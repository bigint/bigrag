from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from bigrag import __version__
from bigrag.middleware.auth import get_current_user

router = APIRouter(tags=["health"])

_embedding_health_cache: dict[str, tuple[bool, float]] = {}
_EMBEDDING_HEALTH_TTL = 60  # seconds


async def _check_embedding_provider(settings) -> dict[str, bool]:
    """Validate embedding provider connectivity by embedding a test string."""
    provider = settings.embedding_provider
    api_key = settings.embedding_api_key

    if not api_key:
        return {"embedding": False, "embedding_error": "no API key configured"}

    now = time.monotonic()
    cached = _embedding_health_cache.get(provider)
    if cached and (now - cached[1]) < _EMBEDDING_HEALTH_TTL:
        return {"embedding": cached[0]}

    try:
        from bigrag.services.embedding import get_embedding_model

        model = get_embedding_model(
            provider=provider,
            model_name=settings.embedding_model,
            dimension=settings.embedding_dimension,
            api_key=api_key,
        )
        await asyncio.wait_for(model.embed(["health check"], input_type="query"), timeout=10)
        _embedding_health_cache[provider] = (True, now)
        return {"embedding": True}
    except Exception as exc:
        _embedding_health_cache[provider] = (False, now)
        return {"embedding": False, "embedding_error": str(exc)[:200]}


@router.get("/health")
async def health():
    return {"status": "ok", "version": __version__}


@router.get("/health/ready")
async def readiness(request: Request):
    db = request.app.state.db
    vs = request.app.state.vector_store
    queue = request.app.state.queue
    s = request.app.state.settings

    checks: dict[str, object] = {"version": __version__}
    healthy = True

    async def _check_postgres():
        await db.fetchrow("SELECT 1")

    async def _check_milvus():
        if vs.client:
            from pymilvus import MilvusClient

            if isinstance(vs.client, MilvusClient):
                vs.client.list_collections()
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

    for name, result in zip(infra_checks.keys(), results):
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
):
    db = request.app.state.db
    queue = request.app.state.queue

    async def _db_stats():
        cols = await db.fetchrow("SELECT COUNT(*) as cnt FROM collections")
        docs = await db.fetchrow(
            "SELECT COUNT(*) as total, "
            "COALESCE(SUM(file_size), 0) as total_size, "
            "COALESCE(SUM(chunk_count), 0) as total_chunks, "
            "COALESCE(SUM(token_count), 0) as total_tokens, "
            "COUNT(*) FILTER (WHERE status = 'ready') as ready, "
            "COUNT(*) FILTER (WHERE status = 'pending') as pending, "
            "COUNT(*) FILTER (WHERE status = 'processing') as processing, "
            "COUNT(*) FILTER (WHERE status = 'failed') as failed "
            "FROM documents"
        )
        webhooks = await db.fetchrow("SELECT COUNT(*) as cnt FROM webhooks")
        return cols, docs, webhooks

    async def _queue_stats():
        return await queue.stats

    (cols, docs, webhooks), queue_stats = await asyncio.gather(_db_stats(), _queue_stats())

    return {
        "collections": cols["cnt"],
        "documents": {
            "total": docs["total"],
            "ready": docs["ready"],
            "pending": docs["pending"],
            "processing": docs["processing"],
            "failed": docs["failed"],
            "total_chunks": int(docs["total_chunks"]),
            "total_tokens": int(docs["total_tokens"]),
            "total_size_bytes": int(docs["total_size"]),
        },
        "webhooks": webhooks["cnt"],
        "queue": queue_stats,
    }
