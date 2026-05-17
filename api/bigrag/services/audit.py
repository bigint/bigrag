from __future__ import annotations

import asyncio
import uuid
from typing import Any

import sqlalchemy as sa
from fastapi import Request

from bigrag.db.engine import session_factory
from bigrag.db.models import AuditLog
from bigrag.ids import uuid7
from bigrag.logging import get_logger

logger = get_logger("bigrag.audit")

_AUDIT_QUEUE_MAX = 5000
_AUDIT_BATCH_MAX = 100
_AUDIT_FLUSH_INTERVAL = 0.25
_AUDIT_STOP_TIMEOUT = 5.0

_audit_queue: asyncio.Queue[dict[str, Any]] | None = None
_audit_stop_event: asyncio.Event | None = None
_audit_flusher_task: asyncio.Task | None = None


def _uuid_or_none(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        return None


def _build_row(
    *,
    actor_id: str | None,
    actor_email: str | None,
    api_key_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    metadata: dict,
    ip: str | None,
    user_agent: str | None,
) -> dict[str, Any]:
    return {
        "id": uuid7(),
        "actor_id": _uuid_or_none(actor_id),
        "actor_email": actor_email,
        "api_key_id": _uuid_or_none(api_key_id),
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "meta": metadata,
        "ip": ip,
        "user_agent": user_agent,
    }


def _enqueue(row: dict[str, Any]) -> None:
    queue = _audit_queue
    if queue is None:
        logger.warning(
            "audit: queue not started; dropping record",
            action=row.get("action"),
            resource_type=row.get("resource_type"),
        )
        return
    try:
        queue.put_nowait(row)
    except asyncio.QueueFull:
        logger.warning(
            "audit: queue full; dropping record",
            action=row.get("action"),
            resource_type=row.get("resource_type"),
            queue_max=_AUDIT_QUEUE_MAX,
        )


async def _drain_batch(queue: asyncio.Queue[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        first = await asyncio.wait_for(queue.get(), timeout=_AUDIT_FLUSH_INTERVAL)
    except TimeoutError:
        return []
    batch = [first]
    while len(batch) < _AUDIT_BATCH_MAX:
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
            await session.execute(sa.insert(AuditLog), batch)
            await session.commit()
    except Exception as exc:
        logger.warning(
            "audit: bulk insert failed — falling back to stderr",
            count=len(batch),
            error=str(exc),
        )


async def _audit_flusher(stop_event: asyncio.Event) -> None:
    queue = _audit_queue
    assert queue is not None
    while not (stop_event.is_set() and queue.empty()):
        try:
            batch = await _drain_batch(queue)
            if batch:
                await _flush_batch(batch)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("audit: flusher iteration failed", error=str(exc))


async def start_audit_flusher() -> None:
    global _audit_queue, _audit_stop_event, _audit_flusher_task
    if _audit_flusher_task is not None and not _audit_flusher_task.done():
        return
    _audit_queue = asyncio.Queue(maxsize=_AUDIT_QUEUE_MAX)
    _audit_stop_event = asyncio.Event()
    _audit_flusher_task = asyncio.create_task(
        _audit_flusher(_audit_stop_event),
        name="audit_flusher",
    )


async def stop_audit_flusher() -> None:
    global _audit_queue, _audit_stop_event, _audit_flusher_task
    task = _audit_flusher_task
    stop_event = _audit_stop_event
    queue = _audit_queue
    if task is None or stop_event is None or queue is None:
        return
    stop_event.set()
    try:
        await asyncio.wait_for(task, timeout=_AUDIT_STOP_TIMEOUT)
    except TimeoutError:
        logger.warning("audit: flusher shutdown timed out; cancelling")
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
    _audit_flusher_task = None
    _audit_stop_event = None
    _audit_queue = None


async def flush_audit_logs() -> None:
    queue = _audit_queue
    if queue is None:
        return
    while not queue.empty():
        batch: list[dict[str, Any]] = []
        while len(batch) < _AUDIT_BATCH_MAX:
            try:
                batch.append(queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        if batch:
            await _flush_batch(batch)


def record(
    request: Request,
    *,
    user: dict | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:

    from bigrag.services.client_ip import client_ip

    ip = client_ip(request)
    user_agent = request.headers.get("user-agent")
    actor_id = user.get("id") if user else None
    actor_email = user.get("email") if user else None
    api_key_id = user.get("api_key_id") if user else None

    _enqueue(
        _build_row(
            actor_id=actor_id,
            actor_email=actor_email,
            api_key_id=api_key_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata or {},
            ip=ip,
            user_agent=user_agent,
        )
    )
