from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def encode_message(message: dict[str, Any]) -> dict[str, Any]:
    return jsonable_encoder(message)


def subscribed(subscription_id: str, topic: str) -> dict[str, Any]:
    return {
        "type": "subscribed",
        "id": subscription_id,
        "topic": topic,
        "generated_at": now_iso(),
    }


def snapshot(subscription_id: str, topic: str, payload: Any) -> dict[str, Any]:
    return {
        "type": "snapshot",
        "id": subscription_id,
        "topic": topic,
        "payload": payload,
        "generated_at": now_iso(),
    }


def event(subscription_id: str, topic: str, payload: Any) -> dict[str, Any]:
    return {
        "type": "event",
        "id": subscription_id,
        "topic": topic,
        "payload": payload,
        "generated_at": now_iso(),
    }


def error(subscription_id: str | None, topic: str | None, message: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": "error",
        "message": message,
        "generated_at": now_iso(),
    }
    if subscription_id is not None:
        data["id"] = subscription_id
    if topic is not None:
        data["topic"] = topic
    return data


def complete(subscription_id: str, topic: str) -> dict[str, Any]:
    return {
        "type": "complete",
        "id": subscription_id,
        "topic": topic,
        "generated_at": now_iso(),
    }


def heartbeat() -> dict[str, Any]:
    return {"type": "heartbeat", "generated_at": now_iso()}


def pong() -> dict[str, Any]:
    return {"type": "pong", "generated_at": now_iso()}
