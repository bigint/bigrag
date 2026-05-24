from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from bigrag.services.connectors.realtime import (
    connector_sources_event_key,
    connector_sync_jobs_event_key,
)
from bigrag.services.connectors.views import (
    connector_sources_payload,
    connector_sync_jobs_payload,
)
from bigrag.services.realtime.admin_topics._session import with_session
from bigrag.services.realtime.params import integer, string
from bigrag.services.realtime.specs import SnapshotTopic

ACTIVE_SYNC_JOB_STATUSES = {"pending", "running"}


def _connector_sources_topic(
    websocket: WebSocket, user: dict, params: dict[str, Any]
) -> SnapshotTopic:
    provider = string(params, "provider", required=True, max_length=80)
    collection = string(params, "collection", max_length=120)
    snapshot_topic = f"{provider}:sources:{collection or 'all'}"

    async def load():
        return await with_session(
            lambda session: connector_sources_payload(
                session,
                provider_slug=provider,
                collection=collection,
            )
        )

    return SnapshotTopic(
        snapshot_topic,
        load,
        _connector_sources_interval,
        connector_sources_event_key(provider, collection),
    )


def _connector_jobs_topic(
    websocket: WebSocket, user: dict, params: dict[str, Any]
) -> SnapshotTopic:
    provider = string(params, "provider", required=True, max_length=80)
    collection = string(params, "collection", max_length=120)
    source_id = string(params, "source_id", max_length=120)
    limit = integer(params, "limit", default=20, minimum=1, maximum=100)
    snapshot_topic = f"{provider}:sync-jobs:{collection or 'all'}:{source_id or 'all'}"

    async def load():
        return await with_session(
            lambda session: connector_sync_jobs_payload(
                session,
                provider_slug=provider,
                collection=collection,
                source_id=source_id,
                limit=limit,
            )
        )

    return SnapshotTopic(
        snapshot_topic,
        load,
        _connector_jobs_interval,
        connector_sync_jobs_event_key(provider, collection, source_id),
    )


def _connector_sources_interval(payload: Any | None) -> float:
    sources = getattr(payload, "sources", []) if payload is not None else []
    return 2.5 if any(getattr(source, "status", None) == "syncing" for source in sources) else 10.0


def _connector_jobs_interval(payload: Any | None) -> float:
    jobs = getattr(payload, "jobs", []) if payload is not None else []
    return (
        2.5
        if any(getattr(job, "status", None) in ACTIVE_SYNC_JOB_STATUSES for job in jobs)
        else 10.0
    )
