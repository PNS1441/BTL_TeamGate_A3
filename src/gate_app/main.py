"""
FIT4110 Lab 04 — Access Gate Service (team-gate)
Dockerized FastAPI service aligned with the Lab 03 OpenAPI contract.
Endpoints: /health, /access-events, /cards
"""

import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

from gate_app.mqtt_client import start_mqtt_background

# ──────────────────────────────────────────────
# Config from environment
# ──────────────────────────────────────────────
SERVICE_NAME = os.getenv("SERVICE_NAME", "access-gate")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.4.0")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "local-dev-token")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi động MQTT client ngầm
    thread = start_mqtt_background()
    yield
    # Có thể thêm logic dọn dẹp ở đây nếu cần

# ──────────────────────────────────────────────
# App
# ──────────────────────────────────────────────
app = FastAPI(
    lifespan=lifespan,
    title="FIT4110 Lab 04 — Access Gate Service",
    version=SERVICE_VERSION,
    description=(
        "Dockerized Access Gate API — team-gate. "
        "Manages RFID card swipe events at campus gates. "
        "Aligned with Lab 03 OpenAPI contract."
    ),
)

# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────
class Direction(str, Enum):
    in_ = "in"
    out = "out"


class AccessResult(str, Enum):
    accepted = "accepted"
    denied = "denied"
    error = "error"


class DenyReason(str, Enum):
    invalid_card = "invalid_card"
    expired_card = "expired_card"
    permission_denied = "permission_denied"
    gate_error = "gate_error"
    unknown = "unknown"


class CardStatus(str, Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"


# ──────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────
class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int = Field(..., ge=400, le=599)
    detail: str
    instance: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class AccessEventCreate(BaseModel):
    card_id: str = Field(..., min_length=3, examples=["CARD-2026-001"])
    gate_id: str = Field(..., min_length=1, examples=["GATE-01"])
    direction: Direction = Field(..., examples=["in"])
    timestamp: str = Field(..., examples=["2026-05-19T08:30:00Z"])


class AccessEventResult(BaseModel):
    event_id: str
    card_id: str
    gate_id: str
    direction: Direction
    result: AccessResult
    deny_reason: Optional[DenyReason] = None
    zone_id: Optional[str] = None
    timestamp: str
    created_at: str


class CardCreate(BaseModel):
    holder_name: str = Field(..., min_length=2, examples=["Nguyen Van B"])
    expires_at: str = Field(..., examples=["2027-06-01T00:00:00Z"])


class Card(BaseModel):
    card_id: str
    holder_name: str
    status: CardStatus
    issued_at: str
    expires_at: str


# ──────────────────────────────────────────────
# In-memory stores
# ──────────────────────────────────────────────
ACCESS_EVENTS: List[Dict] = []

# Seeded card database
CARDS: Dict[str, Dict] = {
    "CARD-2026-001": {
        "card_id": "CARD-2026-001",
        "holder_name": "Nguyen Van A",
        "status": "active",
        "issued_at": "2026-01-15T00:00:00Z",
        "expires_at": "2027-01-15T00:00:00Z",
    },
    "CARD-2026-002": {
        "card_id": "CARD-2026-002",
        "holder_name": "Tran Thi B",
        "status": "active",
        "issued_at": "2026-02-01T00:00:00Z",
        "expires_at": "2027-02-01T00:00:00Z",
    },
    "CARD-EXPIRED-001": {
        "card_id": "CARD-EXPIRED-001",
        "holder_name": "Le Van C",
        "status": "expired",
        "issued_at": "2024-01-01T00:00:00Z",
        "expires_at": "2025-01-01T00:00:00Z",
    },
}

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"


def next_event_id() -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"EVT-{today}-{len(ACCESS_EVENTS) + 1:04d}"


def build_problem(
    *,
    status_code: int,
    title: str,
    detail: str,
    instance: Optional[str] = None,
    problem_type: str = "about:blank",
) -> Dict:
    problem = {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance:
        problem["instance"] = instance
    return problem


def evaluate_card(card_id: str):
    """Evaluate whether a card should be accepted or denied."""
    card = CARDS.get(card_id)
    if card is None:
        return AccessResult.denied, DenyReason.invalid_card
    if card["status"] == "expired":
        return AccessResult.denied, DenyReason.expired_card
    if card["status"] == "revoked":
        return AccessResult.denied, DenyReason.permission_denied
    return AccessResult.accepted, None


# ──────────────────────────────────────────────
# Exception handlers
# ──────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        problem = exc.detail
    else:
        problem = build_problem(
            status_code=exc.status_code,
            title=str(exc.status_code),
            detail=str(exc.detail),
            instance=str(request.url.path),
        )

    problem.setdefault("status", exc.status_code)
    problem.setdefault("title", str(exc.status_code))
    problem.setdefault("type", "about:blank")
    problem.setdefault("detail", "Request failed")
    problem.setdefault("instance", str(request.url.path))

    return JSONResponse(
        status_code=exc.status_code,
        content=problem,
        media_type="application/problem+json",
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first_error = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(item) for item in first_error.get("loc", []))
    message = first_error.get("msg", "Request validation error")
    detail = f"{location}: {message}" if location else message

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=build_problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Validation error",
            detail=detail,
            instance=str(request.url.path),
            problem_type="https://smart-campus.local/problems/validation-error",
        ),
        media_type="application/problem+json",
    )


# ──────────────────────────────────────────────
# Auth dependency
# ──────────────────────────────────────────────
def verify_bearer_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Missing Authorization header",
                instance="/access-events",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )
    expected = f"Bearer {AUTH_TOKEN}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=build_problem(
                status_code=status.HTTP_401_UNAUTHORIZED,
                title="Unauthorized",
                detail="Invalid bearer token",
                instance="/access-events",
                problem_type="https://smart-campus.local/problems/unauthorized",
            ),
        )


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
    )


@app.post(
    "/access-events",
    response_model=AccessEventResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
    responses={
        401: {"model": ProblemDetails},
        422: {"model": ProblemDetails},
    },
)
def create_access_event(payload: AccessEventCreate) -> AccessEventResult:
    result, deny_reason = evaluate_card(payload.card_id)
    event_id = next_event_id()
    created_at = now_iso()
    zone_id = "ZONE-A"  # Default zone for lab

    item = {
        "event_id": event_id,
        "card_id": payload.card_id,
        "gate_id": payload.gate_id,
        "direction": payload.direction.value,
        "result": result.value,
        "deny_reason": deny_reason.value if deny_reason else None,
        "zone_id": zone_id,
        "timestamp": payload.timestamp,
        "created_at": created_at,
    }
    ACCESS_EVENTS.append(item)

    return AccessEventResult(
        event_id=event_id,
        card_id=payload.card_id,
        gate_id=payload.gate_id,
        direction=payload.direction,
        result=result,
        deny_reason=deny_reason,
        zone_id=zone_id,
        timestamp=payload.timestamp,
        created_at=created_at,
    )


@app.get(
    "/access-events",
    dependencies=[Depends(verify_bearer_token)],
    responses={401: {"model": ProblemDetails}},
)
def get_access_events(
    gate_id: Optional[str] = Query(default=None),
    direction: Optional[str] = Query(default=None),
    result: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Dict:
    items = list(ACCESS_EVENTS)

    if gate_id:
        items = [e for e in items if e["gate_id"] == gate_id]
    if direction:
        items = [e for e in items if e["direction"] == direction]
    if result:
        items = [e for e in items if e["result"] == result]

    total = len(items)
    paginated = items[offset: offset + limit]

    return {"items": paginated, "total": total}


@app.get(
    "/cards/{card_id}",
    response_model=Card,
    dependencies=[Depends(verify_bearer_token)],
    responses={
        401: {"model": ProblemDetails},
        404: {"model": ProblemDetails},
    },
)
def get_card_by_id(card_id: str) -> Card:
    card = CARDS.get(card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=build_problem(
                status_code=status.HTTP_404_NOT_FOUND,
                title="Not Found",
                detail=f"Card {card_id} not found",
                instance=f"/cards/{card_id}",
                problem_type="https://smart-campus.local/problems/not-found",
            ),
        )
    return Card(**card)


@app.post(
    "/cards",
    response_model=Card,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_bearer_token)],
    responses={
        400: {"model": ProblemDetails},
        401: {"model": ProblemDetails},
    },
)
def create_card(payload: CardCreate, response: Response) -> Card:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    card_id = f"CARD-{today}-{len(CARDS) + 1:03d}"
    issued_at = now_iso()

    card = {
        "card_id": card_id,
        "holder_name": payload.holder_name,
        "status": "active",
        "issued_at": issued_at,
        "expires_at": payload.expires_at,
    }
    CARDS[card_id] = card
    response.headers["Location"] = f"/cards/{card_id}"
    return Card(**card)
