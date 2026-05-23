from __future__ import annotations

import re
from typing import Any

import sqlalchemy as sa
from fastapi import WebSocket

from bigrag.db.engine import session_factory
from bigrag.db.models import Collection
from bigrag.services.realtime.auth import authorize_collection_events
from bigrag.services.realtime.params import string
from bigrag.services.realtime.specs import EventTopic, TopicError

_COLLECTION_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")


async def collection_events_topic(
    websocket: WebSocket,
    principal: dict | None,
    params: dict[str, Any],
) -> EventTopic:
    collection = string(
        params, "collection", required=True, max_length=120, pattern=_COLLECTION_NAME
    )
    token = string(params, "token", max_length=500)
    await authorize_collection_events(websocket, principal, collection, token)
    async with session_factory()() as session:
        exists = await session.scalar(sa.select(Collection.id).where(Collection.name == collection))
    if exists is None:
        raise TopicError("Collection not found")
    return EventTopic(
        topic=f"collection.events:{collection}",
        event_key=f"collection:{collection}",
        connected_payload={
            "step": "connected",
            "status": "connected",
            "message": f"Listening for events on {collection}",
            "progress": 0,
        },
    )
