import os
import csv
import json
import ssl
import threading
import time
import uuid
import requests
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MQTT")

MQTT_HOST = os.getenv("MQTT_HOST", "f6f78e87db4a4c189dd3d706745a5e93.s1.eu.hivemq.cloud")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "DVKN2026")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "ThaiBao12A@")
CORE_SERVICE_URL = os.getenv("CORE_SERVICE_URL", "http://26.183.48.228:8000")

TOPIC_RAW = "smart-campus/raw/access/rfid-uid"
TOPIC_EVENTS = "smart-campus/events/access"

# Cache chống spam (Lưu thời gian quẹt cuối cùng của từng UID)
LAST_SWIPE_CACHE = {}

# Load whitelist
WHITELIST = {}
whitelist_path = os.path.join(os.path.dirname(__file__), "uid_whitelist.csv")
try:
    with open(whitelist_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "uid" in row:
                WHITELIST[row["uid"].strip().upper()] = row
    logger.info(f"Loaded {len(WHITELIST)} UIDs from whitelist.")
except Exception as e:
    logger.error(f"Failed to load whitelist: {e}")

def now_iso() -> str:
    # return ISO string with timezone (e.g. 2026-06-07T14:30:11+07:00)
    # Using UTC for simplicity, or we can just append Z
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def process_rfid_event(raw_payload: dict):
    # 1. VALIDATE (Rule 6): Kiểm tra bắt buộc
    required_fields = ["uid", "door_id", "direction"]
    for field in required_fields:
        if field not in raw_payload or not raw_payload[field]:
            raise ValueError(f"Missing required field: {field}")

    raw_uid = raw_payload.get("uid", "").strip().upper()
    door_id = raw_payload.get("door_id", "unknown-gate")
    location = raw_payload.get("location", "Unknown Location")
    direction = raw_payload.get("direction", "in")
    raw_event_id = raw_payload.get("event_id", "")

    event_id = str(uuid.uuid4())

    response_payload = {
        "event_id": event_id,
        "event_type": "access.swipe.processed",
        "source_service": "team-gate",
        "timestamp": now_iso(),
        "raw_event_id": raw_event_id,
        "uid": raw_uid,
        "door_id": door_id,
        "location": location,
        "direction": direction
    }

    # 2. CHỐNG SPAM / QUẸT LIÊN TỤC (Nghiệp vụ nâng cao)
    current_time = time.time()
    if raw_uid in LAST_SWIPE_CACHE:
        time_since_last_swipe = current_time - LAST_SWIPE_CACHE[raw_uid]
        if time_since_last_swipe < 5.0: # Dưới 5 giây
            LAST_SWIPE_CACHE[raw_uid] = current_time
            response_payload.update({"access_result": "denied", "reason": "spam_detected"})
            return response_payload

    LAST_SWIPE_CACHE[raw_uid] = current_time

    # 3. QUY TẮC GIỜ GIỚI NGHIÊM (Nghiệp vụ nâng cao)
    current_hour = datetime.now(timezone.utc).hour # Bạn có thể đổi sang giờ VN bằng cách +7
    # Chặn quẹt thẻ từ 22h đêm đến 4h sáng (ví dụ UTC: 15h đến 21h)
    # Giả sử dùng giờ local của server:
    local_hour = datetime.now().hour
    if local_hour >= 22 or local_hour < 5:
        response_payload.update({"access_result": "denied", "reason": "out_of_hours_restricted"})
        return response_payload

    # 4. LOOKUP & ENRICH (Rule 7, 8, 9)
    student_info = WHITELIST.get(raw_uid)
    subject_id = None
    role = "VISITOR"
    card_status = "REVOKED"
    
    if student_info:
        response_payload.update({
            "student_id": student_info.get("student_id"),
            "full_name": student_info.get("full_name"),
            "class_name": student_info.get("class_name")
        })
        subject_id = student_info.get("student_id")
        role = "STAFF"
        card_status = "ACTIVE"
        access_result = "granted"
        reason = "uid_matched"
    else:
        response_payload.update({
            "student_id": None,
            "full_name": None,
            "class_name": None
        })
        access_result = "denied"
        reason = "uid_not_found"

    # Giao tiếp với Core (Realtime sync)
    core_card_id = "CARD-" + raw_uid.replace(":", "")
    core_payload = {
        "requestId": event_id,
        "cardId": core_card_id,
        "gateId": "GATE-01",
        "direction": "ENTRY" if direction.lower() == "in" else "EXIT",
        "occurredAt": now_iso(),
        "subject": {
            "subjectId": subject_id or "UNKNOWN",
            "role": role,
            "cardStatus": card_status,
            "zone": "ADMIN"
        }
    }
    
    core_headers = {
        "Authorization": "Bearer lab-core-token",
        "Content-Type": "application/json",
        "Idempotency-Key": f"gate-idem-{event_id}"
    }

    try:
        url = f"{CORE_SERVICE_URL.rstrip('/')}/api/v1/access-events"
        logger.info(f"Calling Team Core at {url} for UID {raw_uid}")
        resp = requests.post(url, json=core_payload, headers=core_headers, timeout=3.0)
        if resp.status_code == 200:
            result_data = resp.json().get("result", {})
            decision = result_data.get("decision")
            reason_code = result_data.get("reasonCode", "UNKNOWN")
            
            # Ghi đè quyết định nếu Core từ chối
            if decision != "ALLOW":
                access_result = "denied"
                reason = f"policy_deny_{reason_code}"
        else:
            # Nếu Core lỗi, Fail-closed (chặn luôn)
            access_result = "denied"
            reason = f"core_error_{resp.status_code}"
            logger.error(f"Team Core returned error {resp.status_code}: {resp.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to call Team Core: {e}")
        # Mạng chập chờn -> Fail-closed
        access_result = "denied"
        reason = "core_service_timeout"
        
    response_payload.update({
        "access_result": access_result,
        "reason": reason
    })

    return response_payload

def on_connect(client, userdata, flags, reason_code, properties=None):
    logger.info(f"Connected to HiveMQ with reason code: {reason_code}")
    if reason_code == 0:
        client.subscribe(TOPIC_RAW, qos=1)
        logger.info(f"Subscribed to topic: {TOPIC_RAW}")
    else:
        logger.error(f"Failed to connect. Reason code: {reason_code}")

def on_message(client, userdata, message):
    try:
        payload_str = message.payload.decode("utf-8")
        raw_payload = json.loads(payload_str)
        logger.info(f"Received raw RFID event: {raw_payload.get('uid')}")
        
        response_payload = process_rfid_event(raw_payload)
        
        # Publish the result
        response_str = json.dumps(response_payload)
        client.publish(TOPIC_EVENTS, response_str, qos=1)
        
        # Save to API's in-memory storage so Team Core can query it
        try:
            from gate_app.main import ACCESS_EVENTS
            api_item = {
                "event_id": response_payload["event_id"],
                "card_id": response_payload["uid"],
                "gate_id": "GATE-01",
                "direction": "in" if str(response_payload.get("direction", "in")).lower() == "in" else "out",
                "result": "accepted" if response_payload["access_result"] == "granted" else "denied",
                "deny_reason": "permission_denied" if response_payload["access_result"] != "granted" else None,
                "zone_id": "ZONE-A",
                "timestamp": response_payload["timestamp"],
                "created_at": now_iso()
            }
            ACCESS_EVENTS.append(api_item)
        except Exception as e:
            logger.error(f"Failed to append to ACCESS_EVENTS: {e}")

        logger.info(f"Published access event -> UID: {response_payload['uid']}, Result: {response_payload['access_result']}, Reason: {response_payload.get('reason')}")
        
    except json.JSONDecodeError:
        logger.error("Failed to parse JSON payload.")
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def run_mqtt_client():
    client = mqtt.Client(protocol=mqtt.MQTTv5)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)

    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            logger.info("Attempting to connect to HiveMQ...")
            client.connect(MQTT_HOST, MQTT_PORT)
            client.loop_forever()
        except Exception as e:
            logger.error(f"MQTT connection error: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)

def start_mqtt_background():
    thread = threading.Thread(target=run_mqtt_client, daemon=True)
    thread.start()
    return thread
