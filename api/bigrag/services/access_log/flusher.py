from __future__ import annotations

import asyncio
from typing import Any

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import AccessLog
from bigrag.logging import get_logger

logger = get_logger("bigrag.access_log")

_ACCESS_LOG_QUEUE_MAX = 5000
_ACCESS_LOG_BATCH_MAX = 100
_ACCESS_LOG_FLUSH_INTERVAL = 0.25
_ACCESS_LOG_STOP_TIMEOUT = 5.0

_access_log_queue: asyncio.Queue[dict[str, Any]] | None = None
_access_log_stop_event: asyncio.Event | None = None
_access_log_flusher_task: asyncio.Task | None = None


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


def enqueue(row: dict[str, Any]) -> None:
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
