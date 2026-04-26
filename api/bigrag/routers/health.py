from __future__ import annotations

import asyncio

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

logger = get_logger("bigrag.routers.health")

router = APIRouter(tags=["health"])

_EMBEDDING_HEALTH_TTL = 60  # seconds


async def _resolve_embedding_target(
    settings,
) -> tuple[str, str, int | None, str, str | None] | None:
    """Pick a (provider, model, dimension, api_key, source) tuple to probe.

    Order: global env override → first embedding preset with a key →
    first collection with a key. Returns None when nothing is configured.
    """
    if settings.embedding_api_key:
        return (
            settings.embedding_provider,
            settings.embedding_model,
            settings.embedding_dimension,
            settings.embedding_api_key,
            "env",
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
                "collection",
            )

    return None


async def _check_embedding_provider(settings) -> dict[str, object]:
    """Validate embedding provider connectivity by embedding a test string.

    A bigRAG instance is "healthy" for embeddings if ANY configured source
    (env, preset, or collection) can successfully embed. Reporting "down"
    when only the env var is missing — but presets work — is misleading
    and hides the fact that retrieval is actually functional.
    """
    target = await _resolve_embedding_target(settings)
    if target is None:
        return {"embedding": False, "embedding_error": "no API key configured"}

    provider, model, dimension, api_key, source = target
    cache_key = f"health:embedding:{provider}:{source}"
    cached = await redis_cache.get(cache_key)
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
        )
        await asyncio.wait_for(emb_model.embed(["health check"], input_type="query"), timeout=10)
        await redis_cache.set(cache_key, {"ok": True}, ttl=_EMBEDDING_HEALTH_TTL)
        return {"embedding": True, "embedding_source": source}
    except Exception as exc:
        category = _categorize_provider_error(exc)
        await redis_cache.set(
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


def _categorize_provider_error(exc: Exception) -> str:
    text = f"{exc.__class__.__name__}: {exc}".lower()
    if any(t in text for t in _AUTH_TOKENS):
        return "auth_failed"
    if any(t in text for t in _RATE_TOKENS):
        return "rate_limited"
    if any(t in text for t in _TIMEOUT_TOKENS):
        return "timeout"
    if any(t in text for t in _NETWORK_TOKENS):
        return "unreachable"
    return "unknown"


@router.get("/health")
async def health():
    return {"status": "ok", "version": __version__}


@router.get("/health/ready")
async def readiness(request: Request):
    vs = request.app.state.vector_store
    queue = request.app.state.queue
    s = request.app.state.settings

    checks: dict[str, object] = {"version": __version__}
    healthy = True

    async def _check_postgres():
        async with session_factory()() as session:
            await session.execute(sa.text("SELECT 1"))

    async def _check_milvus():
        if vs.client:
            from pymilvus import MilvusClient

            if isinstance(vs.client, MilvusClient):
                await asyncio.to_thread(vs.client.list_collections)
        else:
            raise RuntimeError("milvus client not connected")

    async def _check_redis():
        await queue._redis.ping()

    infra_checks = {
        "postgres": _check_postgres(),
        "milvus": _check_milvus(),
        "redis": _check_redis(),
    }

    results = await asyncio.gather(
        *infra_checks.values(),
        return_exceptions=True,
    )

    for name, result in zip(infra_checks.keys(), results, strict=False):
        if isinstance(result, Exception):
            checks[name] = False
            healthy = False
        else:
            checks[name] = True

    embedding_result = await _check_embedding_provider(s)
    checks.update(embedding_result)
    if not embedding_result.get("embedding"):
        healthy = False

    checks["status"] = "ok" if healthy else "degraded"
    return JSONResponse(content=checks, status_code=200 if healthy else 503)


@router.get("/v1/stats")
async def platform_stats(
    request: Request,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    cached = await redis_cache.get("stats:platform")
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

    (cols, docs, webhooks), queue_stats = await asyncio.gather(_db_stats(), _queue_stats())

    result = {
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
    }
    await redis_cache.set("stats:platform", result, ttl=15)
    return result
