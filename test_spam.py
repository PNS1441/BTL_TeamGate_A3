import paho.mqtt.client as mqtt
import json
import time
import ssl

# Cấu hình HiveMQ
MQTT_HOST = "f6f78e87db4a4c189dd3d706745a5e93.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USERNAME = "DVKN2026"
MQTT_PASSWORD = "ThaiBao12A@"
TOPIC = "smart-campus/raw/access/rfid-uid"

payload = {
    "uid": "04:A1:B2:C3:D4:01",
    "door_id": "GATE-01",
    "direction": "in"
}

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected! Sending spam simulation...")
        
        # Lần quẹt 1
        print("[Event 1] Valid swipe...")
        client.publish(TOPIC, json.dumps(payload), qos=1)
        
        time.sleep(1) # Chờ 1 giây
        
        # Lần quẹt 2 (Cố tình spam)
        print("[Event 2] Immediate swipe to test Anti-Spam...")
        client.publish(TOPIC, json.dumps(payload), qos=1)
        
        time.sleep(2)
        print("Done! Check your other terminal.")
        client.disconnect()

client = mqtt.Client(protocol=mqtt.MQTTv5)
client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
client.on_connect = on_connect

client.connect(MQTT_HOST, MQTT_PORT)
client.loop_forever()
