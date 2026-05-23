from __future__ import annotations

from typing import Any

from fastapi import HTTPException, WebSocket

from bigrag.services.realtime.admin_topics import admin_topic
from bigrag.services.realtime.auth import authorize_admin
from bigrag.services.realtime.collection_topics import collection_events_topic
from bigrag.services.realtime.specs import RealtimeTopic, TopicError


async def resolve_topic(
    websocket: WebSocket,
    principal: dict | None,
    topic: str,
    params: dict[str, Any],
) -> RealtimeTopic:
    if topic == "collection.events":
        return await collection_events_topic(websocket, principal, params)
    await authorize_admin(principal)
    return admin_topic(websocket, principal or {}, topic, params)


def topic_error_message(exc: Exception) -> str:
    if isinstance(exc, TopicError | HTTPException | PermissionError):
        detail = getattr(exc, "detail", None)
        if isinstance(detail, str):
            return detail
        return str(exc) or "Realtime subscription failed"
    return "Realtime subscription failed"
