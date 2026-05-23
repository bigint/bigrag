from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection, Document, Webhook
from bigrag.services.health import cache_get, cache_set
from bigrag.services.jobs.broker import INGESTION_QUEUE, worker_heartbeat_key

PLATFORM_STATS_CACHE_KEY = "stats:platform"
PLATFORM_STATS_TTL = 15


async def platform_stats_payload(
    queue: Any,
    session: AsyncSession,
    *,
    use_cache: bool = True,
) -> dict[str, object]:
    if use_cache:
        cached = await cache_get(PLATFORM_STATS_CACHE_KEY)
        if cached:
            return cached

    async def db_stats():
        cols = await session.scalar(sa.select(sa.func.count()).select_from(Collection))
        doc_row = (
            await session.execute(
                sa.select(
                    sa.func.count().label("total"),
                    sa.func.coalesce(sa.func.sum(Document.file_size), 0).label("total_size"),
                    sa.func.coalesce(sa.func.sum(Document.chunk_count), 0).label("total_chunks"),
                    sa.func.coalesce(sa.func.sum(Document.token_count), 0).label("total_tokens"),
                    sa.func.count().filter(Document.status == "ready").label("ready"),
                    sa.func.count().filter(Document.status == "pending").label("pending"),
                    sa.func.count().filter(Document.status == "processing").label("processing"),
                    sa.func.count().filter(Document.status == "failed").label("failed"),
                )
            )
        ).one()
        webhooks = await session.scalar(sa.select(sa.func.count()).select_from(Webhook))
        return cols or 0, doc_row, webhooks or 0

    async def queue_stats():
        return await queue.stats

    async def worker_stats():
        heartbeat = None
        redis = getattr(queue, "redis", None)
        if redis is not None and hasattr(redis, "get"):
            raw = await redis.get(worker_heartbeat_key(INGESTION_QUEUE))
            if raw is not None:
                heartbeat = raw.decode() if isinstance(raw, bytes) else str(raw)
        online = False
        age = None
        if heartbeat:
            try:
                parsed = datetime.fromisoformat(heartbeat)
                age = max(0, int((datetime.now(UTC) - parsed).total_seconds()))
                online = age < 120
            except ValueError:
                online = False
        return {
            "online": online,
            "status": "online" if online else "offline",
            "heartbeat_at": heartbeat,
            "heartbeat_age_seconds": age,
        }

    db_result, queue_result, worker_result = await asyncio.gather(
        db_stats(), queue_stats(), worker_stats(), return_exceptions=True
    )
    if isinstance(db_result, BaseException):
        raise db_result
    cols, docs, webhooks = db_result
    queue_data = {} if isinstance(queue_result, BaseException) else queue_result
    worker_data = (
        {
            "online": False,
            "status": "offline",
            "heartbeat_at": None,
            "heartbeat_age_seconds": None,
        }
        if isinstance(worker_result, BaseException)
        else worker_result
    )

    queue_health = queue_health_payload(queue_data, worker_data)
    result = {
        "status": queue_health["status"],
        "collections": cols,
        "documents": {
            "total": docs.total,
            "ready": docs.ready,
            "pending": docs.pending,
            "processing": docs.processing,
            "failed": docs.failed,
            "total_chunks": int(docs.total_chunks),
            "total_tokens": int(docs.total_tokens),
            "total_size_bytes": int(docs.total_size),
        },
        "webhooks": webhooks,
        "queue": queue_data,
        "queue_health": queue_health,
        "workers": worker_data,
    }
    if use_cache:
        await cache_set(PLATFORM_STATS_CACHE_KEY, result, ttl=PLATFORM_STATS_TTL)
    return result


def queue_int(stats: dict, key: str) -> int:
    try:
        return int(stats.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def queue_health_payload(stats: dict, worker_stats: dict) -> dict[str, object]:
    reasons: list[str] = []
    pending = queue_int(stats, "pending")
    processing = queue_int(stats, "processing")
    retrying = queue_int(stats, "retrying")
    dead_lettered = queue_int(stats, "dead_lettered")
    stale_processing = queue_int(stats, "stale_processing")
    active = pending + processing + retrying
    worker_online = bool(worker_stats.get("online"))

    if not worker_online and active > 0:
        reasons.append("worker_offline_with_active_queue")
    elif not worker_online:
        reasons.append("worker_offline")
    if dead_lettered > 0:
        reasons.append("dead_lettered_jobs")
    if stale_processing > 0:
        reasons.append("stale_processing_jobs")
    if retrying > 0:
        reasons.append("retrying_jobs")

    if "worker_offline_with_active_queue" in reasons:
        status = "down"
    elif reasons:
        status = "degraded"
    else:
        status = "ok"

    return {"status": status, "reasons": reasons}
