from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder

PROTOCOL_VERSION = 1


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def encode_message(message: dict[str, Any]) -> dict[str, Any]:
    return jsonable_encoder(message)


def _envelope(message_type: str, **fields: Any) -> dict[str, Any]:
    return {
        "type": message_type,
        "version": PROTOCOL_VERSION,
        **fields,
        "generated_at": now_iso(),
    }


def subscribed(subscription_id: str, topic: str) -> dict[str, Any]:
    return _envelope("subscribed", id=subscription_id, topic=topic)


def snapshot(subscription_id: str, topic: str, payload: Any) -> dict[str, Any]:
    return _envelope("snapshot", id=subscription_id, topic=topic, payload=payload)


def event(subscription_id: str, topic: str, payload: Any) -> dict[str, Any]:
    return _envelope("event", id=subscription_id, topic=topic, payload=payload)


def error(subscription_id: str | None, topic: str | None, message: str) -> dict[str, Any]:
    return _envelope("error", id=subscription_id, topic=topic, message=message)


def complete(subscription_id: str, topic: str) -> dict[str, Any]:
    return _envelope("complete", id=subscription_id, topic=topic)


def heartbeat() -> dict[str, Any]:
    return _envelope("heartbeat")


def pong() -> dict[str, Any]:
    return _envelope("pong")
