from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag import __version__
from bigrag.db.engine import session_factory
from bigrag.db.models import Collection, Document, Webhook
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.services import redis_cache
from bigrag.services.jobs.broker import WORKER_HEARTBEAT_KEY
from bigrag.services.runtime_settings import get_values

logger = get_logger("bigrag.routers.health")

router = APIRouter(tags=["health"])

_EMBEDDING_HEALTH_TTL = 60
_READINESS_TTL = 10
_READINESS_CACHE_KEY = "health:readiness"


async def _cache_get(key: str) -> dict | list | None:
    try:
        return await redis_cache.get(key)
    except Exception as exc:
        logger.warning("health cache get failed", key=key, error=repr(exc))
        return None


async def _cache_set(key: str, value: dict | list, ttl: int) -> None:
    try:
        await redis_cache.set(key, value, ttl=ttl)
    except Exception as exc:
        logger.warning("health cache set failed", key=key, error=repr(exc))


async def _resolve_embedding_target() -> (
    tuple[str, str, int | None, str, str | None, str | None] | None
):
    runtime = await get_values(
        [
            "embedding_provider",
            "embedding_model",
            "embedding_dimension",
            "embedding_api_key",
            "embedding_base_url",
        ]
    )

    if runtime["embedding_api_key"]:
        return (
            runtime["embedding_provider"],
            runtime["embedding_model"],
            runtime["embedding_dimension"],
            runtime["embedding_api_key"],
            runtime["embedding_base_url"],
            "settings",
        )

    from bigrag.db.models import Collection, EmbeddingPreset

    async with session_factory()() as session:
        preset = await session.scalar(
            sa.select(EmbeddingPreset)
            .where(EmbeddingPreset.api_key.is_not(None))
            .where(EmbeddingPreset.api_key != "")
            .order_by(EmbeddingPreset.created_at.asc())
            .limit(1)
        )
        if preset is not None:
            return (
                preset.provider,
                preset.model,
                preset.dimension,
                preset.api_key,
                preset.base_url,
                "preset",
            )

        collection = await session.scalar(
            sa.select(Collection)
            .where(Collection.embedding_api_key.is_not(None))
            .where(Collection.embedding_api_key != "")
            .order_by(Collection.created_at.asc())
            .limit(1)
        )
        if collection is not None:
            return (
                collection.embedding_provider,
                collection.embedding_model,
                collection.dimension,
                collection.embedding_api_key,
                collection.embedding_base_url,
                "collection",
            )

    return None


async def _check_embedding_provider() -> dict[str, object]:

    target = await _resolve_embedding_target()
    if target is None:
        return {"embedding": False, "embedding_error": "no API key configured"}

    provider, model, dimension, api_key, base_url, source = target
    cache_key = f"health:embedding:{provider}:{source}"
    cached = await _cache_get(cache_key)
    if cached:
        result: dict[str, object] = {"embedding": cached["ok"], "embedding_source": source}
        if cached.get("error"):
            result["embedding_error"] = cached["error"]
        return result

    try:
        from bigrag.services.embedding import get_embedding_model

        emb_model = get_embedding_model(
            provider=provider,
            model_name=model,
            dimension=dimension,
            api_key=api_key,
            base_url=base_url,
        )
        await asyncio.wait_for(emb_model.embed(["health check"], input_type="query"), timeout=10)
        await _cache_set(cache_key, {"ok": True}, ttl=_EMBEDDING_HEALTH_TTL)
        return {"embedding": True, "embedding_source": source}
    except Exception as exc:
        category = _categorize_provider_error(exc)
        await _cache_set(
            cache_key,
            {"ok": False, "error": category},
            ttl=_EMBEDDING_HEALTH_TTL,
        )
        logger.warning(
            "embedding health check failed",
            provider=provider,
            source=source,
            category=category,
            error=repr(exc),
        )
        return {
            "embedding": False,
            "embedding_error": category,
            "embedding_source": source,
        }


_AUTH_TOKENS = ("401", "unauthor", "invalid api key", "invalid_api_key")
_RATE_TOKENS = ("429", "rate", "quota")
_TIMEOUT_TOKENS = ("timeout", "timed out")
_NETWORK_TOKENS = ("connection", "network", "unreachable", "dns")
_MISCONFIGURED_TOKENS = (
    "not configured",
    "client not connected",
    "invalid url",
    "missing",
    "misconfigured",
)


def _categorize_dependency_error(exc: Exception) -> str:
    text = f"{exc.__class__.__name__}: {exc}".lower()
    if any(t in text for t in _AUTH_TOKENS):
        return "auth_failed"
    if any(t in text for t in _RATE_TOKENS):
        return "rate_limited"
    if any(t in text for t in _TIMEOUT_TOKENS):
        return "timeout"
    if any(t in text for t in _NETWORK_TOKENS):
        return "unreachable"
    if any(t in text for t in _MISCONFIGURED_TOKENS):
        return "misconfigured"
    return "unknown"


def _categorize_provider_error(exc: Exception) -> str:
    return _categorize_dependency_error(exc)


@router.get("/health", response_model=dict[str, str])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/health/ready", response_model=dict[str, object])
async def readiness(request: Request) -> JSONResponse:
    cached = await _cache_get(_READINESS_CACHE_KEY)
    if cached:
        status = cached.get("status")
        return JSONResponse(content=cached, status_code=200 if status == "ok" else 503)

    vs = request.app.state.vector_store
    queue = request.app.state.queue

    checks: dict[str, object] = {"version": __version__}
    healthy = True

    async def _check_postgres():
        async with session_factory()() as session:
            await session.execute(sa.text("SELECT 1"))

    async def _check_vector_store():
        if vs.client:
            await vs.health_check()
        else:
            raise RuntimeError("vector store client not connected")

    async def _check_redis():
        redis = getattr(queue, "redis", None) or getattr(queue, "_redis", None)
        await redis.ping()

    infra_checks = {
        "postgres": _check_postgres(),
        "vector_store": _check_vector_store(),
        "redis": _check_redis(),
    }

    results = await asyncio.gather(
        *infra_checks.values(),
        return_exceptions=True,
    )

    for name, result in zip(infra_checks.keys(), results, strict=False):
        if isinstance(result, Exception):
            checks[name] = False
            checks[f"{name}_error"] = _categorize_dependency_error(result)
            healthy = False
        else:
            checks[name] = True
    checks["vector_store_provider"] = "per_collection"
    checks["qdrant"] = (
        checks["vector_store"] if "qdrant" in getattr(vs, "configured_providers", ()) else None
    )

    embedding_result = await _check_embedding_provider()
    checks.update(embedding_result)
    if not embedding_result.get("embedding"):
        healthy = False

    checks["status"] = "ok" if healthy else "degraded"
    await _cache_set(_READINESS_CACHE_KEY, checks, ttl=_READINESS_TTL)
    return JSONResponse(content=checks, status_code=200 if healthy else 503)


@router.get("/v1/stats", response_model=dict[str, object])
async def platform_stats(
    request: Request,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    cached = await _cache_get("stats:platform")
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
    await _cache_set("stats:platform", result, ttl=15)
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
