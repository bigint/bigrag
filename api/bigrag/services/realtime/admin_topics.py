from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket

from bigrag.db.engine import session_factory
from bigrag.services.access_log.queries import access_logs_payload, access_overview_payload
from bigrag.services.audit import audit_log_payload
from bigrag.services.backup.views import backup_jobs_payload
from bigrag.services.collection_stats import collection_stats_payload
from bigrag.services.connectors.realtime import (
    connector_sources_event_key,
    connector_sync_jobs_event_key,
)
from bigrag.services.connectors.views import (
    connector_sources_payload,
    connector_sync_jobs_payload,
)
from bigrag.services.document_batch import batch_status_payload
from bigrag.services.document_progress import TERMINAL_DOCUMENT_STATUSES
from bigrag.services.documents import get_document_payload, list_documents_payload
from bigrag.services.event_bus import INGESTION_EVENTS_KEY
from bigrag.services.health import readiness_payload
from bigrag.services.platform_stats import platform_stats_payload
from bigrag.services.realtime.params import boolean, document_ids, integer, string
from bigrag.services.realtime.specs import SnapshotTopic, TopicError, fixed
from bigrag.services.upload_sessions import upload_session_payload
from bigrag.services.usage import usage_payload

ACTIVE_SYNC_JOB_STATUSES = {"pending", "running"}
ACTIVE_BACKUP_JOB_STATUSES = {"pending", "running"}

TopicBuilder = Callable[[WebSocket, dict, dict[str, Any]], SnapshotTopic]


def admin_topic(websocket: WebSocket, user: dict, topic: str, params: dict[str, Any]):
    builder = _TOPIC_BUILDERS.get(topic)
    if builder is None:
        raise TopicError("Unknown realtime topic")
    return builder(websocket, user, params)


def _documents_topic(websocket: WebSocket, user: dict, params: dict[str, Any]) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    q = string(params, "q", max_length=200)
    status = string(params, "status")
    sort = string(params, "sort", default="created_at") or "created_at"
    order = string(params, "order", default="desc") or "desc"
    include_total = boolean(params, "include_total") or False
    limit = integer(params, "limit", default=100, minimum=1, maximum=1000)
    offset = integer(params, "offset", default=0, minimum=0)
    snapshot_topic = f"documents:list:{collection}"

    async def load():
        return await with_session(
            lambda session: list_documents_payload(
                session,
                collection_name=collection,
                q=q,
                status=status,
                sort=sort,
                order=order,
                limit=limit,
                offset=offset,
                cursor=None,
                include_total=include_total,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(5.0), f"collection:{collection}")


def _batch_status_topic(websocket: WebSocket, user: dict, params: dict[str, Any]) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    ids = document_ids(params.get("document_ids"))
    snapshot_topic = f"documents:batch:{collection}:{','.join(ids)}"

    async def load():
        return await with_session(
            lambda session: batch_status_payload(
                session,
                user=user,
                collection_name=collection,
                document_ids=ids,
            )
        )

    return SnapshotTopic(
        snapshot_topic,
        load,
        fixed(2.0),
        f"collection:{collection}",
        lambda payload: _batch_done(payload, len(ids)),
    )


def _document_topic(websocket: WebSocket, user: dict, params: dict[str, Any]) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    document_id = string(params, "document_id", required=True, max_length=120)
    snapshot_topic = f"documents:detail:{collection}:{document_id}"

    async def load():
        return await with_session(
            lambda session: get_document_payload(
                session,
                user=user,
                collection_name=collection,
                document_id=document_id,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(2.0), document_id, _document_done)


def _upload_session_topic(
    websocket: WebSocket, user: dict, params: dict[str, Any]
) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    session_id = string(params, "session_id", required=True, max_length=120)
    snapshot_topic = f"upload-session:{collection}:{session_id}"

    async def load():
        return await with_session(
            lambda session: upload_session_payload(
                session,
                user=user,
                collection_name=collection,
                session_id=session_id,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(2.0), None, _upload_session_done)


def _collection_stats_topic(
    websocket: WebSocket, user: dict, params: dict[str, Any]
) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    snapshot_topic = f"collections:stats:{collection}"

    async def load():
        return await with_session(
            lambda session: collection_stats_payload(session, name=collection)
        )

    return SnapshotTopic(snapshot_topic, load, fixed(10.0), f"collection:{collection}")


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


def _access_overview_topic(
    websocket: WebSocket, user: dict, params: dict[str, Any]
) -> SnapshotTopic:
    window_days = integer(params, "window_days", default=7, minimum=1, maximum=90)
    snapshot_topic = f"access:overview:{window_days}"

    async def load():
        return await with_session(
            lambda session: access_overview_payload(session, window_days=window_days)
        )

    return SnapshotTopic(snapshot_topic, load, fixed(20.0))


def _access_logs_topic(websocket: WebSocket, user: dict, params: dict[str, Any]) -> SnapshotTopic:
    action = string(params, "action", max_length=100)
    actor_id = string(params, "actor_id", max_length=120)
    collection = string(params, "collection", max_length=120)
    method = string(params, "method", max_length=10)
    path = string(params, "path", max_length=300)
    status_family = string(params, "status_family", max_length=3)
    success = boolean(params, "success")
    limit = integer(params, "limit", default=100, minimum=1, maximum=1000)
    offset = integer(params, "offset", default=0, minimum=0)
    if status_family is not None and status_family not in {"1xx", "2xx", "3xx", "4xx", "5xx"}:
        raise TopicError("status_family must be one of 1xx, 2xx, 3xx, 4xx, or 5xx")
    snapshot_topic = ":".join(
        [
            "access:logs",
            action or "*",
            actor_id or "*",
            collection or "*",
            method or "*",
            path or "*",
            status_family or "*",
            str(success),
            str(limit),
            str(offset),
        ]
    )

    async def load():
        return await with_session(
            lambda session: access_logs_payload(
                session,
                action=action,
                actor_id=actor_id,
                collection=collection,
                method=method,
                path=path,
                status_family=status_family,
                success=success,
                limit=limit,
                offset=offset,
                cursor=None,
                include_total=False,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(20.0))


def _audit_topic(websocket: WebSocket, user: dict, params: dict[str, Any]) -> SnapshotTopic:
    action = string(params, "action", max_length=100)
    actor_id = string(params, "actor_id", max_length=120)
    resource_type = string(params, "resource_type", max_length=50)
    limit = integer(params, "limit", default=100, minimum=1, maximum=1000)
    offset = integer(params, "offset", default=0, minimum=0)
    snapshot_topic = (
        f"audit:{action or '*'}:{actor_id or '*'}:{resource_type or '*'}:{limit}:{offset}"
    )

    async def load():
        return await with_session(
            lambda session: audit_log_payload(
                session,
                action=action,
                actor_id=actor_id,
                resource_type=resource_type,
                limit=limit,
                offset=offset,
                cursor=None,
                include_total=False,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(60.0))


def _usage_topic(websocket: WebSocket, user: dict, params: dict[str, Any]) -> SnapshotTopic:
    window_days = integer(params, "window_days", default=30, minimum=1, maximum=365)
    snapshot_topic = f"usage:{window_days}"

    async def load():
        return await with_session(lambda session: usage_payload(session, window_days=window_days))

    return SnapshotTopic(snapshot_topic, load, fixed(60.0))


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


_TOPIC_BUILDERS: dict[str, TopicBuilder] = {
    "admin.collections.documents": _documents_topic,
    "admin.collections.documents.batch_status": _batch_status_topic,
    "admin.collections.documents.detail": _document_topic,
    "admin.collections.upload_session": _upload_session_topic,
    "admin.collections.stats": _collection_stats_topic,
    "admin.connectors.sources": _connector_sources_topic,
    "admin.connectors.sync_jobs": _connector_jobs_topic,
    "admin.backups": _backups_topic,
    "admin.access.overview": _access_overview_topic,
    "admin.access.logs": _access_logs_topic,
    "admin.audit": _audit_topic,
    "admin.usage": _usage_topic,
    "admin.platform.stats": _platform_stats_topic,
    "admin.platform.readiness": _platform_readiness_topic,
}


def _document_done(payload: Any) -> bool:
    return getattr(payload, "status", None) in TERMINAL_DOCUMENT_STATUSES


def _batch_done(payload: Any, expected_count: int) -> bool:
    documents = getattr(payload, "documents", [])
    terminal = all(
        getattr(document, "status", None) in TERMINAL_DOCUMENT_STATUSES for document in documents
    )
    if len(documents) < expected_count:
        return terminal
    return bool(documents) and terminal


def _upload_session_done(payload: Any) -> bool:
    return getattr(payload, "status", None) in {"complete", "failed", "canceled"}


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


def _backup_jobs_interval(payload: Any | None) -> float:
    jobs = getattr(payload, "jobs", []) if payload is not None else []
    active = any(getattr(job, "status", None) in ACTIVE_BACKUP_JOB_STATUSES for job in jobs)
    return 2.0 if active else 15.0


async def with_session(load: Callable[[Any], Awaitable[Any]]) -> Any:
    async with session_factory()() as session:
        return await load(session)
