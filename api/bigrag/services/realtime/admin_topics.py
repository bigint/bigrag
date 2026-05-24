from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket

from bigrag.db.engine import session_factory
from bigrag.models.document import BatchStatusRequest
from bigrag.routers.admin_access import access_overview, list_access_logs
from bigrag.routers.admin_audit import list_audit_log
from bigrag.routers.admin_backups import list_backup_jobs
from bigrag.routers.collections import get_collection_stats
from bigrag.routers.connectors import connector_sources, connector_sync_jobs
from bigrag.routers.documents import get_document, list_documents
from bigrag.routers.documents_batch import batch_get_status
from bigrag.routers.documents_progress import TERMINAL_DOCUMENT_STATUSES
from bigrag.routers.health import readiness
from bigrag.routers.upload_sessions import get_upload_session as upload_session_detail
from bigrag.routers.usage import get_usage
from bigrag.services.connectors.realtime import (
    connector_sources_event_key,
    connector_sync_jobs_event_key,
)
from bigrag.services.event_bus import INGESTION_EVENTS_KEY
from bigrag.services.platform_stats import platform_stats_payload
from bigrag.services.realtime.params import boolean, document_ids, integer, string
from bigrag.services.realtime.specs import SnapshotTopic, TopicError, fixed

ACTIVE_SYNC_JOB_STATUSES = {"pending", "running"}
ACTIVE_BACKUP_JOB_STATUSES = {"pending", "running"}


def admin_topic(websocket: WebSocket, user: dict, topic: str, params: dict[str, Any]):
    if topic == "admin.collections.documents":
        return _documents_topic(user, params)
    if topic == "admin.collections.documents.batch_status":
        return _batch_status_topic(user, params)
    if topic == "admin.collections.documents.detail":
        return _document_topic(user, params)
    if topic == "admin.collections.upload_session":
        return _upload_session_topic(user, params)
    if topic == "admin.collections.stats":
        return _collection_stats_topic(user, params)
    if topic == "admin.connectors.sources":
        return _connector_sources_topic(user, params)
    if topic == "admin.connectors.sync_jobs":
        return _connector_jobs_topic(user, params)
    if topic == "admin.backups":
        return _backups_topic(user, params)
    if topic == "admin.access.overview":
        return _access_overview_topic(user, params)
    if topic == "admin.access.logs":
        return _access_logs_topic(user, params)
    if topic == "admin.audit":
        return _audit_topic(user, params)
    if topic == "admin.usage":
        return _usage_topic(user, params)
    if topic == "admin.platform.stats":
        return _platform_stats_topic(websocket, user)
    if topic == "admin.platform.readiness":
        return _platform_readiness_topic(websocket)
    raise TopicError("Unknown realtime topic")


def _documents_topic(user: dict, params: dict[str, Any]) -> SnapshotTopic:
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
            lambda session: list_documents(
                collection_name=collection,
                q=q,
                status=status,
                sort=sort,
                order=order,
                limit=limit,
                offset=offset,
                cursor=None,
                include_total=include_total,
                _=user,
                session=session,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(5.0), f"collection:{collection}")


def _batch_status_topic(user: dict, params: dict[str, Any]) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    ids = document_ids(params.get("document_ids"))
    snapshot_topic = f"documents:batch:{collection}:{','.join(ids)}"

    async def load():
        return await with_session(
            lambda session: batch_get_status(
                collection_name=collection,
                body=BatchStatusRequest(document_ids=ids),
                user=user,
                session=session,
            )
        )

    return SnapshotTopic(
        snapshot_topic,
        load,
        fixed(2.0),
        f"collection:{collection}",
        lambda payload: _batch_done(payload, len(ids)),
    )


def _document_topic(user: dict, params: dict[str, Any]) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    document_id = string(params, "document_id", required=True, max_length=120)
    snapshot_topic = f"documents:detail:{collection}:{document_id}"

    async def load():
        return await with_session(
            lambda session: get_document(
                collection_name=collection,
                document_id=document_id,
                user=user,
                session=session,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(2.0), document_id, _document_done)


def _upload_session_topic(user: dict, params: dict[str, Any]) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    session_id = string(params, "session_id", required=True, max_length=120)
    snapshot_topic = f"upload-session:{collection}:{session_id}"

    async def load():
        return await with_session(
            lambda session: upload_session_detail(
                collection_name=collection,
                session_id=session_id,
                user=user,
                db=session,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(2.0), None, _upload_session_done)


def _collection_stats_topic(user: dict, params: dict[str, Any]) -> SnapshotTopic:
    collection = string(params, "collection", required=True, max_length=120)
    snapshot_topic = f"collections:stats:{collection}"

    async def load():
        return await with_session(
            lambda session: get_collection_stats(name=collection, user=user, session=session)
        )

    return SnapshotTopic(snapshot_topic, load, fixed(10.0), f"collection:{collection}")


def _connector_sources_topic(user: dict, params: dict[str, Any]) -> SnapshotTopic:
    provider = string(params, "provider", required=True, max_length=80)
    collection = string(params, "collection", max_length=120)
    snapshot_topic = f"{provider}:sources:{collection or 'all'}"

    async def load():
        return await with_session(
            lambda session: connector_sources(
                provider_slug=provider,
                collection=collection,
                user=user,
                session=session,
            )
        )

    return SnapshotTopic(
        snapshot_topic,
        load,
        _connector_sources_interval,
        connector_sources_event_key(provider, collection),
    )


def _connector_jobs_topic(user: dict, params: dict[str, Any]) -> SnapshotTopic:
    provider = string(params, "provider", required=True, max_length=80)
    collection = string(params, "collection", max_length=120)
    source_id = string(params, "source_id", max_length=120)
    limit = integer(params, "limit", default=20, minimum=1, maximum=100)
    snapshot_topic = f"{provider}:sync-jobs:{collection or 'all'}:{source_id or 'all'}"

    async def load():
        return await with_session(
            lambda session: connector_sync_jobs(
                provider_slug=provider,
                collection=collection,
                source_id=source_id,
                limit=limit,
                user=user,
                session=session,
            )
        )

    return SnapshotTopic(
        snapshot_topic,
        load,
        _connector_jobs_interval,
        connector_sync_jobs_event_key(provider, collection, source_id),
    )


def _backups_topic(user: dict, params: dict[str, Any]) -> SnapshotTopic:
    limit = integer(params, "limit", default=20, minimum=1, maximum=100)
    offset = integer(params, "offset", default=0, minimum=0)
    snapshot_topic = f"backups:{limit}:{offset}"

    async def load():
        return await with_session(
            lambda session: list_backup_jobs(
                limit=limit,
                offset=offset,
                cursor=None,
                include_total=False,
                _=user,
                session=session,
            )
        )

    return SnapshotTopic(snapshot_topic, load, _backup_jobs_interval)


def _access_overview_topic(user: dict, params: dict[str, Any]) -> SnapshotTopic:
    window_days = integer(params, "window_days", default=7, minimum=1, maximum=90)
    snapshot_topic = f"access:overview:{window_days}"

    async def load():
        return await with_session(
            lambda session: access_overview(window_days=window_days, _=user, session=session)
        )

    return SnapshotTopic(snapshot_topic, load, fixed(20.0))


def _access_logs_topic(user: dict, params: dict[str, Any]) -> SnapshotTopic:
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
            lambda session: list_access_logs(
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
                _=user,
                session=session,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(20.0))


def _audit_topic(user: dict, params: dict[str, Any]) -> SnapshotTopic:
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
            lambda session: list_audit_log(
                action=action,
                actor_id=actor_id,
                resource_type=resource_type,
                limit=limit,
                offset=offset,
                cursor=None,
                include_total=False,
                _=user,
                session=session,
            )
        )

    return SnapshotTopic(snapshot_topic, load, fixed(60.0))


def _usage_topic(user: dict, params: dict[str, Any]) -> SnapshotTopic:
    window_days = integer(params, "window_days", default=30, minimum=1, maximum=365)
    snapshot_topic = f"usage:{window_days}"

    async def load():
        return await with_session(
            lambda session: get_usage(window_days=window_days, _=user, session=session)
        )

    return SnapshotTopic(snapshot_topic, load, fixed(60.0))


def _platform_stats_topic(websocket: WebSocket, _user: dict) -> SnapshotTopic:
    async def load():
        return await with_session(
            lambda session: platform_stats_payload(
                websocket.app.state.queue,
                session,
                use_cache=False,
            )
        )

    return SnapshotTopic("platform:stats", load, fixed(5.0), INGESTION_EVENTS_KEY)


def _platform_readiness_topic(websocket: WebSocket) -> SnapshotTopic:
    async def load():
        response = await readiness(websocket)
        return json.loads(response.body)

    return SnapshotTopic("platform:readiness", load, fixed(10.0))


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
