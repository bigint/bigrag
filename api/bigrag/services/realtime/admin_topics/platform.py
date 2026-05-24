from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from bigrag.services.backup.views import backup_jobs_payload
from bigrag.services.event_bus import INGESTION_EVENTS_KEY
from bigrag.services.health import readiness_payload
from bigrag.services.platform_stats import platform_stats_payload
from bigrag.services.realtime.admin_topics._session import with_session
from bigrag.services.realtime.params import integer
from bigrag.services.realtime.specs import SnapshotTopic, fixed

ACTIVE_BACKUP_JOB_STATUSES = {"pending", "running"}


def _backups_topic(websocket: WebSocket, user: dict, params: dict[str, Any]) -> SnapshotTopic:
    limit = integer(params, "limit", default=20, minimum=1, maximum=100)
    offset = integer(params, "offset", default=0, minimum=0)
    snapshot_topic = f"backups:{limit}:{offset}"

    async def load():
        return await with_session(
            lambda session: backup_jobs_payload(
                session,
                limit=limit,
                offset=offset,
                cursor=None,
                include_total=False,
            )
        )

    return SnapshotTopic(snapshot_topic, load, _backup_jobs_interval)


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


def _backup_jobs_interval(payload: Any | None) -> float:
    jobs = getattr(payload, "jobs", []) if payload is not None else []
    active = any(getattr(job, "status", None) in ACTIVE_BACKUP_JOB_STATUSES for job in jobs)
    return 2.0 if active else 15.0
