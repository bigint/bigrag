from __future__ import annotations

import asyncio
from typing import Any

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import Collection, QueryLog
from bigrag.logging import get_logger
from bigrag.services.error_sanitize import sanitize_message_text

logger = get_logger("bigrag.retrieval")

_QUERY_LOG_QUEUE_MAX = 5000
_QUERY_LOG_BATCH_MAX = 100
_QUERY_LOG_FLUSH_INTERVAL = 0.25
_QUERY_LOG_STOP_TIMEOUT = 5.0

_query_log_queue: asyncio.Queue[dict[str, Any]] | None = None
_query_log_stop_event: asyncio.Event | None = None
_query_log_flusher_task: asyncio.Task | None = None


def log_retrieval_start(
    *,
    collection_name: str,
    top_k: int,
    search_mode: str,
) -> None:
    logger.info(f"{collection_name} | searching | {search_mode} top {top_k}")


def log_retrieval_cache_hit(
    *,
    collection_name: str,
    result_count: int,
    total_ms: float,
) -> None:
    logger.info(f"{collection_name} | cached | {result_count} results in {total_ms:.0f}ms")


def log_retrieval_complete(
    *,
    collection_name: str,
    result_count: int,
    timings: dict[str, float],
) -> None:
    total_ms = timings.get("total_ms", 0)
    logger.info(f"{collection_name} | found {result_count} results in {total_ms:.0f}ms")


def log_retrieval_failed(
    *,
    collection_name: str,
    elapsed_ms: float,
    exc: Exception,
) -> None:
    error = sanitize_message_text(str(exc)) or exc.__class__.__name__
    logger.warning(f"{collection_name} | search failed after {elapsed_ms:.0f}ms | {error}")


def log_query(
    collection_name: str,
    query: str,
    top_k: int,
    result_count: int,
    avg_score: float | None,
    latency_ms: float,
    search_mode: str,
    collection_id: str | None = None,
) -> None:
    queue = _query_log_queue
    if queue is None:
        return
    row = {
        "collection_id": collection_id,
        "collection_name": collection_name,
        "query": query[:500],
        "top_k": top_k,
        "result_count": result_count,
        "avg_score": avg_score,
        "latency_ms": latency_ms,
        "search_mode": search_mode,
    }
    try:
        queue.put_nowait(row)
    except asyncio.QueueFull:
        logger.warning("query_log: queue full; dropping record", collection=collection_name)


async def _drain_batch(queue: asyncio.Queue[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        first = await asyncio.wait_for(queue.get(), timeout=_QUERY_LOG_FLUSH_INTERVAL)
    except TimeoutError:
        return []
    batch = [first]
    while len(batch) < _QUERY_LOG_BATCH_MAX:
        try:
            batch.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    return batch


async def _resolve_collection_ids(session: Any, batch: list[dict[str, Any]]) -> None:
    names = {
        row["collection_name"]
        for row in batch
        if row.get("collection_id") is None and row.get("collection_name")
    }
    if not names:
        return
    result = await session.execute(
        sa.select(Collection.id, Collection.name).where(Collection.name.in_(names))
    )
    id_by_name = {name: cid for cid, name in result.all()}
    for row in batch:
        if row.get("collection_id") is None:
            row["collection_id"] = id_by_name.get(row["collection_name"])


async def _flush_batch(batch: list[dict[str, Any]]) -> None:
    if not batch:
        return
    try:
        async with session_factory()() as session:
            await _resolve_collection_ids(session, batch)
            await session.execute(sa.insert(QueryLog), batch)
            await session.commit()
    except Exception as exc:
        logger.warning("query_log: bulk insert failed", count=len(batch), error=str(exc))


async def _query_log_flusher(stop_event: asyncio.Event) -> None:
    queue = _query_log_queue
    assert queue is not None
    while not (stop_event.is_set() and queue.empty()):
        try:
            batch = await _drain_batch(queue)
            if batch:
                await _flush_batch(batch)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("query_log: flusher iteration failed", error=str(exc))


async def start_query_log_flusher() -> None:
    global _query_log_queue, _query_log_stop_event, _query_log_flusher_task
    if _query_log_flusher_task is not None and not _query_log_flusher_task.done():
        return
    _query_log_queue = asyncio.Queue(maxsize=_QUERY_LOG_QUEUE_MAX)
    _query_log_stop_event = asyncio.Event()
    _query_log_flusher_task = asyncio.create_task(
        _query_log_flusher(_query_log_stop_event),
        name="query_log_flusher",
    )


async def stop_query_log_flusher() -> None:
    global _query_log_queue, _query_log_stop_event, _query_log_flusher_task
    task = _query_log_flusher_task
    stop_event = _query_log_stop_event
    queue = _query_log_queue
    if task is None or stop_event is None or queue is None:
        return
    stop_event.set()
    try:
        await asyncio.wait_for(task, timeout=_QUERY_LOG_STOP_TIMEOUT)
    except TimeoutError:
        logger.warning("query_log: flusher shutdown timed out; cancelling")
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
    _query_log_flusher_task = None
    _query_log_stop_event = None
    _query_log_queue = None
