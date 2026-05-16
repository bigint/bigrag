from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import orjson
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from bigrag.db.engine import session_factory
from bigrag.middleware.auth import require_admin_session
from bigrag.models.document import BatchStatusRequest
from bigrag.routers.admin_access import access_overview, list_access_logs
from bigrag.routers.admin_audit import list_audit_log
from bigrag.routers.admin_backups import list_backup_jobs
from bigrag.routers.collections import get_collection_stats
from bigrag.routers.connectors import connector_sources, connector_sync_jobs
from bigrag.routers.documents import batch_get_status, get_document, list_documents
from bigrag.routers.health import platform_stats, readiness
from bigrag.routers.upload_sessions import get_upload_session as upload_session_detail
from bigrag.routers.usage import get_usage
from bigrag.services.event_bus import event_bus

router = APIRouter(prefix="/v1/admin/realtime", tags=["admin:realtime"])

HEARTBEAT_SECONDS = 30.0
TERMINAL_DOCUMENT_STATUSES = {"ready", "failed"}
ACTIVE_SYNC_JOB_STATUSES = {"pending", "running"}
ACTIVE_BACKUP_JOB_STATUSES = {"pending", "running"}

SnapshotLoader = Callable[[], Awaitable[Any]]
SnapshotDone = Callable[[Any], bool]
SnapshotInterval = Callable[[Any | None], float]


def _json(value: Any) -> str:
    return orjson.dumps(jsonable_encoder(value)).decode()


def _event_frame(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {_json(data)}\n\n"


def _snapshot_frame(topic: str, payload: Any) -> str:
    return _event_frame(
        "snapshot",
        {
            "topic": topic,
            "payload": payload,
            "generated_at": datetime.now(UTC).isoformat(),
        },
    )


def _error_frame(topic: str, message: str) -> str:
    return _event_frame(
        "error",
        {
            "topic": topic,
            "message": message,
        },
    )


def _heartbeat() -> str:
    return ": heartbeat\n\n"


async def _load_frame(topic: str, load: SnapshotLoader) -> tuple[str, Any | None]:
    try:
        payload = await load()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        return _error_frame(topic, str(exc)), None
    return _snapshot_frame(topic, payload), payload


async def _interval_stream(
    topic: str,
    load: SnapshotLoader,
    interval_for: SnapshotInterval,
    done: SnapshotDone | None = None,
):
    while True:
        frame, payload = await _load_frame(topic, load)
        yield frame
        if payload is not None and done is not None and done(payload):
            break
        remaining = max(1.0, interval_for(payload))
        while remaining > 0:
            delay = min(HEARTBEAT_SECONDS, remaining)
            await asyncio.sleep(delay)
            remaining -= delay
            if remaining > 0:
                yield _heartbeat()


async def _event_stream(
    topic: str,
    load: SnapshotLoader,
    event_key: str,
    interval_for: SnapshotInterval,
    done: SnapshotDone | None = None,
):
    frame, payload = await _load_frame(topic, load)
    yield frame
    if payload is not None and done is not None and done(payload):
        return

    queue = event_bus.subscribe(event_key)
    last_snapshot = time.monotonic()
    try:
        while True:
            interval = max(1.0, interval_for(payload))
            elapsed = time.monotonic() - last_snapshot
            timeout = min(HEARTBEAT_SECONDS, max(0.1, interval - elapsed))
            try:
                marker = await asyncio.wait_for(queue.get(), timeout=timeout)
            except TimeoutError:
                if time.monotonic() - last_snapshot >= interval:
                    frame, payload = await _load_frame(topic, load)
                    last_snapshot = time.monotonic()
                    yield frame
                    if payload is not None and done is not None and done(payload):
                        break
                else:
                    yield _heartbeat()
                continue

            frame, payload = await _load_frame(topic, load)
            last_snapshot = time.monotonic()
            yield frame
            if marker is None:
                if payload is None or done is None or done(payload):
                    break
                continue
            if payload is not None and done is not None and done(payload):
                break
    finally:
        event_bus.unsubscribe(event_key, queue)


def _stream_response(stream) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _interval_response(
    topic: str,
    load: SnapshotLoader,
    interval_for: SnapshotInterval,
    done: SnapshotDone | None = None,
) -> StreamingResponse:
    return _stream_response(_interval_stream(topic, load, interval_for, done))


def _event_response(
    topic: str,
    load: SnapshotLoader,
    event_key: str,
    interval_for: SnapshotInterval,
    done: SnapshotDone | None = None,
) -> StreamingResponse:
    return _stream_response(_event_stream(topic, load, event_key, interval_for, done))


async def _with_session(load: Callable[[Any], Awaitable[Any]]) -> Any:
    async with session_factory()() as session:
        return await load(session)


def _fixed(seconds: float) -> SnapshotInterval:
    return lambda _payload: seconds


def _parse_document_ids(document_ids: list[str]) -> list[str]:
    parsed = [value.strip() for raw in document_ids for value in raw.split(",") if value.strip()]
    if not parsed:
        raise HTTPException(status_code=400, detail="document_ids is required")
    if len(parsed) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 documents per stream")
    return parsed


def _document_done(payload: Any) -> bool:
    return getattr(payload, "status", None) in TERMINAL_DOCUMENT_STATUSES


def _batch_done(payload: Any) -> bool:
    documents = getattr(payload, "documents", [])
    return bool(documents) and all(
        getattr(document, "status", None) in TERMINAL_DOCUMENT_STATUSES for document in documents
    )


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


@router.get("/collections/{collection_name}/documents", response_class=StreamingResponse)
async def collection_documents_stream(
    collection_name: str,
    q: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None),
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_admin_session),
):
    topic = f"documents:list:{collection_name}"

    async def load():
        return await _with_session(
            lambda session: list_documents(
                collection_name=collection_name,
                q=q,
                status=status,
                sort=sort,
                order=order,
                limit=limit,
                offset=offset,
                _=user,
                session=session,
            )
        )

    return _event_response(topic, load, f"collection:{collection_name}", _fixed(5.0))


@router.get(
    "/collections/{collection_name}/documents/batch-status",
    response_class=StreamingResponse,
)
async def collection_documents_batch_status_stream(
    collection_name: str,
    document_ids: list[str] = Query(default_factory=list),
    user: dict = Depends(require_admin_session),
):
    ids = _parse_document_ids(document_ids)
    topic = f"documents:batch:{collection_name}:{','.join(ids)}"

    async def load():
        return await _with_session(
            lambda session: batch_get_status(
                collection_name=collection_name,
                body=BatchStatusRequest(document_ids=ids),
                _=user,
                session=session,
            )
        )

    return _event_response(topic, load, f"collection:{collection_name}", _fixed(2.0), _batch_done)


@router.get(
    "/collections/{collection_name}/documents/{document_id}", response_class=StreamingResponse
)
async def collection_document_stream(
    collection_name: str,
    document_id: str,
    user: dict = Depends(require_admin_session),
):
    topic = f"documents:detail:{collection_name}:{document_id}"

    async def load():
        return await _with_session(
            lambda session: get_document(
                collection_name=collection_name,
                document_id=document_id,
                _=user,
                session=session,
            )
        )

    return _event_response(topic, load, document_id, _fixed(2.0), _document_done)


@router.get(
    "/collections/{collection_name}/upload-sessions/{session_id}",
    response_class=StreamingResponse,
)
async def collection_upload_session_stream(
    collection_name: str,
    session_id: str,
    user: dict = Depends(require_admin_session),
):
    topic = f"upload-session:{collection_name}:{session_id}"

    async def load():
        return await _with_session(
            lambda session: upload_session_detail(
                collection_name=collection_name,
                session_id=session_id,
                user=user,
                db=session,
            )
        )

    return _interval_response(topic, load, _fixed(2.0), _upload_session_done)


@router.get("/collections/{collection_name}/stats", response_class=StreamingResponse)
async def collection_stats_stream(
    collection_name: str,
    user: dict = Depends(require_admin_session),
):
    topic = f"collections:stats:{collection_name}"

    async def load():
        return await _with_session(
            lambda session: get_collection_stats(
                name=collection_name,
                _=user,
                session=session,
            )
        )

    return _event_response(topic, load, f"collection:{collection_name}", _fixed(10.0))


@router.get("/{provider_slug}/sources", response_class=StreamingResponse)
async def connector_sources_stream(
    provider_slug: str,
    collection: str | None = Query(default=None, max_length=120),
    user: dict = Depends(require_admin_session),
):
    topic = f"{provider_slug}:sources:{collection or 'all'}"

    async def load():
        return await _with_session(
            lambda session: connector_sources(
                provider_slug=provider_slug,
                collection=collection,
                user=user,
                session=session,
            )
        )

    return _interval_response(topic, load, _connector_sources_interval)


@router.get("/{provider_slug}/sync-jobs", response_class=StreamingResponse)
async def connector_sync_jobs_stream(
    provider_slug: str,
    collection: str | None = Query(default=None, max_length=120),
    source_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(require_admin_session),
):
    topic = f"{provider_slug}:sync-jobs:{collection or 'all'}:{source_id or 'all'}"

    async def load():
        return await _with_session(
            lambda session: connector_sync_jobs(
                provider_slug=provider_slug,
                collection=collection,
                source_id=source_id,
                limit=limit,
                user=user,
                session=session,
            )
        )

    return _interval_response(topic, load, _connector_jobs_interval)


@router.get("/backups", response_class=StreamingResponse)
async def backup_jobs_stream(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_admin_session),
):
    topic = f"backups:{limit}:{offset}"

    async def load():
        return await _with_session(
            lambda session: list_backup_jobs(
                limit=limit,
                offset=offset,
                _=user,
                session=session,
            )
        )

    return _interval_response(topic, load, _backup_jobs_interval)


@router.get("/access/overview", response_class=StreamingResponse)
async def access_overview_stream(
    window_days: int = Query(default=7, ge=1, le=90),
    user: dict = Depends(require_admin_session),
):
    topic = f"access:overview:{window_days}"

    async def load():
        return await _with_session(
            lambda session: access_overview(
                window_days=window_days,
                _=user,
                session=session,
            )
        )

    return _interval_response(topic, load, _fixed(20.0))


@router.get("/access/logs", response_class=StreamingResponse)
async def access_logs_stream(
    action: str | None = Query(default=None, max_length=100),
    actor_id: str | None = Query(default=None),
    collection: str | None = Query(default=None, max_length=120),
    method: str | None = Query(default=None, max_length=10),
    path: str | None = Query(default=None, max_length=300),
    status_family: str | None = Query(default=None, pattern=r"^[1-5]xx$"),
    success: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_admin_session),
):
    topic_parts = [
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
    topic = ":".join(topic_parts)

    async def load():
        return await _with_session(
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
                _=user,
                session=session,
            )
        )

    return _interval_response(topic, load, _fixed(20.0))


@router.get("/audit", response_class=StreamingResponse)
async def audit_stream(
    action: str | None = Query(default=None, max_length=100),
    actor_id: str | None = Query(default=None),
    resource_type: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(require_admin_session),
):
    topic = f"audit:{action or '*'}:{actor_id or '*'}:{resource_type or '*'}:{limit}:{offset}"

    async def load():
        return await _with_session(
            lambda session: list_audit_log(
                action=action,
                actor_id=actor_id,
                resource_type=resource_type,
                limit=limit,
                offset=offset,
                _=user,
                session=session,
            )
        )

    return _interval_response(topic, load, _fixed(60.0))


@router.get("/usage", response_class=StreamingResponse)
async def usage_stream(
    window_days: int = Query(default=30, ge=1, le=365),
    user: dict = Depends(require_admin_session),
):
    topic = f"usage:{window_days}"

    async def load():
        return await _with_session(
            lambda session: get_usage(
                window_days=window_days,
                _=user,
                session=session,
            )
        )

    return _interval_response(topic, load, _fixed(60.0))


@router.get("/platform/stats", response_class=StreamingResponse)
async def platform_stats_stream(
    request: Request,
    user: dict = Depends(require_admin_session),
):
    topic = "platform:stats"

    async def load():
        return await _with_session(
            lambda session: platform_stats(
                request=request,
                _=user,
                session=session,
            )
        )

    return _interval_response(topic, load, _fixed(15.0))


@router.get("/platform/readiness", response_class=StreamingResponse)
async def platform_readiness_stream(
    request: Request,
    _: dict = Depends(require_admin_session),
):
    topic = "platform:readiness"

    async def load():
        response = await readiness(request)
        return json.loads(response.body)

    return _interval_response(topic, load, _fixed(30.0))
