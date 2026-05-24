from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from bigrag.services.event_bus import INGESTION_EVENTS_KEY
from bigrag.services.health import readiness_payload
from bigrag.services.platform_stats import platform_stats_payload
from bigrag.services.realtime.admin_topics._session import with_session
from bigrag.services.realtime.specs import SnapshotTopic, fixed


def _platform_stats_topic(
    websocket: WebSocket, user: dict, params: dict[str, Any]
) -> SnapshotTopic:
    async def load():
        return await with_session(
            lambda session: platform_stats_payload(
                websocket.app.state.queue,
                session,
                use_cache=False,
            )
        )

    return SnapshotTopic("platform:stats", load, fixed(5.0), INGESTION_EVENTS_KEY)


def _platform_readiness_topic(
    websocket: WebSocket, user: dict, params: dict[str, Any]
) -> SnapshotTopic:
    async def load():
        return await readiness_payload(
            websocket.app.state.vector_store,
            websocket.app.state.queue,
        )

    return SnapshotTopic("platform:readiness", load, fixed(10.0))
