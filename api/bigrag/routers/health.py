from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from bigrag import __version__
from bigrag.deps import get_db, get_queue, get_vector_store
from bigrag.middleware.auth import get_current_user

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "version": __version__}


@router.get("/health/ready")
async def readiness(request: Request):
    db = request.app.state.db
    vs = request.app.state.vector_store
    queue = request.app.state.queue

    checks = {"version": __version__}
    healthy = True

    try:
        await db.fetchrow("SELECT 1")
        checks["postgres"] = True
    except Exception:
        checks["postgres"] = False
        healthy = False

    try:
        if vs.client:
            from pymilvus import MilvusClient

            if isinstance(vs.client, MilvusClient):
                vs.client.list_collections()
            checks["milvus"] = True
        else:
            checks["milvus"] = False
            healthy = False
    except Exception:
        checks["milvus"] = False
        healthy = False

    try:
        await queue._redis.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False
        healthy = False

    status = "ok" if healthy else "degraded"
    checks["status"] = status
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
