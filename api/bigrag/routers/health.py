from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Request
from fastapi.responses import ORJSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag import __version__
from bigrag.db.models import Collection, Document, Webhook
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.services.health import (
    cache_get,
    cache_set,
    readiness_status,
)
from bigrag.services.jobs.broker import WORKER_HEARTBEAT_KEY

logger = get_logger("bigrag.routers.health")

router = APIRouter(tags=["health"])


@router.get("/health", response_model=dict[str, str])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/health/ready", response_model=dict[str, object])
async def readiness(request: Request) -> ORJSONResponse:
    checks, healthy = await readiness_status(
        request.app.state.vector_store,
        request.app.state.queue,
    )
    return ORJSONResponse(content=checks, status_code=200 if healthy else 503)


@router.get("/v1/stats", response_model=dict[str, object])
async def platform_stats(
    request: Request,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    cached = await cache_get("stats:platform")
    if cached:
        return cached

    queue = request.app.state.queue

    async def _db_stats():
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

    async def _queue_stats():
        return await queue.stats

    async def _worker_stats():
        heartbeat = None
        redis = getattr(queue, "redis", None) or getattr(queue, "_redis", None)
        if redis is not None and hasattr(redis, "get"):
            raw = await redis.get(WORKER_HEARTBEAT_KEY)
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

    (cols, docs, webhooks), queue_stats, worker_stats = await asyncio.gather(
        _db_stats(), _queue_stats(), _worker_stats()
    )

    queue_health = _queue_health(queue_stats, worker_stats)
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
        "queue": queue_stats,
        "queue_health": queue_health,
        "workers": worker_stats,
    }
    await cache_set("stats:platform", result, ttl=15)
    return result


def _queue_int(stats: dict, key: str) -> int:
    try:
        return int(stats.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _queue_health(queue_stats: dict, worker_stats: dict) -> dict[str, object]:
    reasons: list[str] = []
    pending = _queue_int(queue_stats, "pending")
    processing = _queue_int(queue_stats, "processing")
    retrying = _queue_int(queue_stats, "retrying")
    dead_lettered = _queue_int(queue_stats, "dead_lettered")
    stale_processing = _queue_int(queue_stats, "stale_processing")
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
