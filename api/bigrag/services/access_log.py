from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa
from starlette.requests import Request
from starlette.types import Receive, Scope, Send

from bigrag.db.engine import session_factory
from bigrag.db.models import AccessLog
from bigrag.ids import uuid7
from bigrag.logging import REQUEST_ID_HEADER, get_logger
from bigrag.services.client_ip import client_ip, client_ip_from_scope

logger = get_logger("bigrag.access_log")

_MAX_METADATA_DEPTH = 4
_MAX_METADATA_ITEMS = 32
_MAX_STRING_LEN = 300
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "cookie",
        "password",
        "prompt",
        "query",
        "secret",
        "session",
        "token",
    }
)
RAG_ACCESS_ACTIONS = frozenset(
    {
        "evaluation.run",
        "chat.generate",
        "query.batch",
        "query.multi",
        "query.run",
        "vectors.delete",
        "vectors.upsert",
    }
)

_ACCESS_LOG_QUEUE_MAX = 5000
_ACCESS_LOG_BATCH_MAX = 100
_ACCESS_LOG_FLUSH_INTERVAL = 0.25
_ACCESS_LOG_STOP_TIMEOUT = 5.0

_access_log_queue: asyncio.Queue[dict[str, Any]] | None = None
_access_log_stop_event: asyncio.Event | None = None
_access_log_flusher_task: asyncio.Task | None = None


def _uuid_or_none(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        return None


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        if len(value) <= _MAX_STRING_LEN:
            return value
        return f"{value[:_MAX_STRING_LEN]}..."
    return str(value)[:_MAX_STRING_LEN]


def _safe_metadata(value: Any, *, depth: int = 0) -> Any:
    if depth >= _MAX_METADATA_DEPTH:
        return "[truncated]"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for idx, (key, item) in enumerate(value.items()):
            if idx >= _MAX_METADATA_ITEMS:
                result["_truncated"] = True
                break
            key_str = str(key)[:80]
            if key_str.lower() in _SENSITIVE_KEYS:
                result[key_str] = "[REDACTED]"
            else:
                result[key_str] = _safe_metadata(item, depth=depth + 1)
        return result
    if isinstance(value, list | tuple | set):
        items = list(value)
        result = [_safe_metadata(item, depth=depth + 1) for item in items[:_MAX_METADATA_ITEMS]]
        if len(items) > _MAX_METADATA_ITEMS:
            result.append("[truncated]")
        return result
    return _safe_scalar(value)


def query_fingerprint(query: str) -> dict[str, int | str]:
    return {
        "query_hash": hashlib.sha256(query.encode("utf-8")).hexdigest()[:24],
        "query_length": len(query),
    }


def filter_summary(filters: dict | None) -> dict[str, Any]:
    if not filters:
        return {"has_filters": False, "filter_keys": []}
    return {
        "has_filters": True,
        "filter_keys": sorted(str(key) for key in filters.keys())[:20],
    }


def set_context(
    request: Request,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    collection_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    context = dict(getattr(request.state, "access_log_context", {}) or {})
    if action is not None:
        context["action"] = action
    if resource_type is not None:
        context["resource_type"] = resource_type
    if resource_id is not None:
        context["resource_id"] = resource_id
    if collection_name is not None:
        context["collection_name"] = collection_name
    if metadata:
        existing = dict(context.get("metadata") or {})
        existing.update(metadata)
        context["metadata"] = existing
    request.state.access_log_context = context


def _infer_action(method: str, path: str) -> tuple[str, str]:
    if path == "/v1/chat" and method == "POST":
        return "chat.generate", "chat"
    if path == "/v1/query" and method == "POST":
        return "query.multi", "collections"
    if path == "/v1/batch/query" and method == "POST":
        return "query.batch", "collections"
    if path == "/v1/evaluation" and method == "POST":
        return "evaluation.run", "collection"
    if path.endswith("/query") and method == "POST":
        return "query.run", "collection"
    if "/vectors/upsert" in path and method == "POST":
        return "vectors.upsert", "collection"
    if "/vectors/delete" in path and method == "POST":
        return "vectors.delete", "collection"
    return "http.request", "http"


def _should_record(scope: Scope) -> bool:
    if scope.get("method") == "OPTIONS":
        return False
    method = str(scope.get("method") or "")
    path = str(scope.get("path") or "")
    action, _ = _infer_action(method, path)
    return action in RAG_ACCESS_ACTIONS


def _build_row(
    *,
    actor_id: str | None,
    actor_email: str | None,
    api_key_id: str | None,
    api_key_name: str | None,
    auth_method: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    collection_name: str | None,
    method: str,
    path: str,
    route: str | None,
    status_code: int,
    latency_ms: float,
    request_id: str | None,
    metadata: dict[str, Any],
    ip: str | None,
    user_agent: str | None,
) -> dict[str, Any]:
    return {
        "id": uuid7(),
        "actor_id": _uuid_or_none(actor_id),
        "actor_email": actor_email,
        "api_key_id": _uuid_or_none(api_key_id),
        "api_key_name": api_key_name,
        "auth_method": auth_method,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "collection_name": collection_name,
        "method": method,
        "path": path,
        "route": route,
        "status_code": status_code,
        "success": 200 <= status_code < 400,
        "latency_ms": latency_ms,
        "request_id": request_id,
        "meta": _safe_metadata(metadata),
        "ip": ip,
        "user_agent": user_agent,
    }


def _enqueue(row: dict[str, Any]) -> None:
    queue = _access_log_queue
    if queue is None:
        logger.warning(
            "access_log: queue not started; dropping record",
            action=row.get("action"),
            path=row.get("path"),
        )
        return
    try:
        queue.put_nowait(row)
    except asyncio.QueueFull:
        logger.warning(
            "access_log: queue full; dropping record",
            action=row.get("action"),
            path=row.get("path"),
            queue_max=_ACCESS_LOG_QUEUE_MAX,
        )


async def _drain_batch(queue: asyncio.Queue[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        first = await asyncio.wait_for(queue.get(), timeout=_ACCESS_LOG_FLUSH_INTERVAL)
    except TimeoutError:
        return []
    batch = [first]
    while len(batch) < _ACCESS_LOG_BATCH_MAX:
        try:
            batch.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    return batch


async def _flush_batch(batch: list[dict[str, Any]]) -> None:
    if not batch:
        return
    try:
        async with session_factory()() as session:
            await session.execute(sa.insert(AccessLog), batch)
            await session.commit()
    except Exception as exc:
        logger.warning(
            "access_log: bulk insert failed",
            count=len(batch),
            error=str(exc),
        )


async def _access_log_flusher(stop_event: asyncio.Event) -> None:
    queue = _access_log_queue
    assert queue is not None
    while not (stop_event.is_set() and queue.empty()):
        try:
            batch = await _drain_batch(queue)
            if batch:
                await _flush_batch(batch)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("access_log: flusher iteration failed", error=str(exc))


async def start_access_log_flusher() -> None:
    global _access_log_queue, _access_log_stop_event, _access_log_flusher_task
    if _access_log_flusher_task is not None and not _access_log_flusher_task.done():
        return
    _access_log_queue = asyncio.Queue(maxsize=_ACCESS_LOG_QUEUE_MAX)
    _access_log_stop_event = asyncio.Event()
    _access_log_flusher_task = asyncio.create_task(
        _access_log_flusher(_access_log_stop_event),
        name="access_log_flusher",
    )


async def stop_access_log_flusher() -> None:
    global _access_log_queue, _access_log_stop_event, _access_log_flusher_task
    task = _access_log_flusher_task
    stop_event = _access_log_stop_event
    queue = _access_log_queue
    if task is None or stop_event is None or queue is None:
        return
    stop_event.set()
    try:
        await asyncio.wait_for(task, timeout=_ACCESS_LOG_STOP_TIMEOUT)
    except TimeoutError:
        logger.warning("access_log: flusher shutdown timed out; cancelling")
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    remaining: list[dict[str, Any]] = []
    while True:
        try:
            remaining.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    if remaining:
        await _flush_batch(remaining)
    _access_log_flusher_task = None
    _access_log_stop_event = None
    _access_log_queue = None


async def flush_access_logs() -> None:
    queue = _access_log_queue
    if queue is None:
        return
    while not queue.empty():
        batch: list[dict[str, Any]] = []
        while len(batch) < _ACCESS_LOG_BATCH_MAX:
            try:
                batch.append(queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if batch:
            await _flush_batch(batch)


class AccessLogMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _should_record(scope):
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        method = str(scope.get("method") or "")
        path = str(scope.get("path") or "")
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            request = Request(scope)
            principal = getattr(request.state, "user", None) or {}
            context = getattr(request.state, "access_log_context", None) or {}
            inferred_action, inferred_resource = _infer_action(method, path)
            route = getattr(scope.get("route"), "path", None)

            metadata = dict(context.get("metadata") or {})
            metadata.setdefault("route", route)
            request_id = getattr(request.state, "request_id", None) or request.headers.get(
                REQUEST_ID_HEADER
            )

            _enqueue(
                _build_row(
                    actor_id=principal.get("id"),
                    actor_email=principal.get("email"),
                    api_key_id=principal.get("api_key_id"),
                    api_key_name=principal.get("api_key_name"),
                    auth_method=principal.get("auth_method"),
                    action=context.get("action") or inferred_action,
                    resource_type=context.get("resource_type") or inferred_resource,
                    resource_id=context.get("resource_id"),
                    collection_name=context.get("collection_name"),
                    method=method,
                    path=path,
                    route=route,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    request_id=request_id,
                    metadata=metadata,
                    ip=client_ip(request) or client_ip_from_scope(scope),
                    user_agent=request.headers.get("user-agent"),
                )
            )
