from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket

from bigrag.db.engine import session_factory
from bigrag.services.realtime.specs import SnapshotTopic

TopicBuilder = Callable[[WebSocket, dict, dict[str, Any]], SnapshotTopic]


async def with_session(load: Callable[[Any], Awaitable[Any]]) -> Any:
    async with session_factory()() as session:
        return await load(session)
