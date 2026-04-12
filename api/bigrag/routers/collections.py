from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.responses import StreamingResponse

from bigrag.config import settings
from bigrag.database import db
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models.collection import (
    CollectionListResponse,
    CollectionResponse,
    CollectionStatsResponse,
    CreateCollectionRequest,
    UpdateCollectionRequest,
)
from bigrag.models.common import StatusResponse
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.routers.collections")

router = APIRouter(prefix="/v1/collections", tags=["collections"])


def _row_to_response(row: dict) -> CollectionResponse:
    data = {k: str(v) if isinstance(v, UUID) else v for k, v in row.items()}
    data["has_api_key"] = bool(data.pop("embedding_api_key", None))
    data.pop("embedding_base_url", None)
    data["has_reranking_api_key"] = bool(data.pop("reranking_api_key", None))
    return CollectionResponse(**data)


@router.get("", response_model=CollectionListResponse)
async def list_collections(
    name: str | None = Query(default=None, description="Filter by name prefix"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(get_current_user),
):
    logger.info(f"list: fetching collections name={name} limit={limit} offset={offset}")
    if name:
        rows = await db.fetch(
            "SELECT * FROM collections WHERE name ILIKE $1"
            " ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            f"{name}%",
            limit,
            offset,
        )
        count_row = await db.fetchrow(
            "SELECT COUNT(*) as cnt FROM collections WHERE name ILIKE $1",
            f"{name}%",
        )
    else:
        rows = await db.fetch(
            "SELECT * FROM collections ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit,
            offset,
        )
        count_row = await db.fetchrow("SELECT COUNT(*) as cnt FROM collections")

    logger.info(f"list: found {len(rows)} collections")
    return CollectionListResponse(
        collections=[_row_to_response(dict(r)) for r in rows],
        total=count_row["cnt"],
    )


@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(body: CreateCollectionRequest, _: dict = Depends(get_current_user)):
    logger.info(
        f"create: name={body.name} provider={body.embedding_provider} model={body.embedding_model}"
    )
    existing = await db.fetchrow("SELECT id FROM collections WHERE name = $1", body.name)
    if existing:
        raise HTTPException(status_code=409, detail="Collection already exists")

    preset: dict | None = None
    if body.embedding_preset_id:
        try:
            preset_uuid = UUID(body.embedding_preset_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid embedding_preset_id") from e
        preset_row = await db.fetchrow(
            "SELECT * FROM embedding_presets WHERE id = $1", preset_uuid
        )
        if not preset_row:
            raise HTTPException(status_code=400, detail="Embedding preset not found")
        preset = dict(preset_row)

    provider = (
        body.embedding_provider
        or (preset["provider"] if preset else None)
        or settings.embedding_provider
    )
    model = (
        body.embedding_model
        or (preset["model"] if preset else None)
        or settings.embedding_model
    )

    if provider not in ("openai", "openai_compatible", "cohere"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported embedding provider: '{provider}'. "
                f"Supported: openai, openai_compatible, cohere"
            ),
        )
    if provider == "openai_compatible":
        if not body.embedding_base_url and not (preset and preset.get("base_url")):
            raise HTTPException(
                status_code=400,
                detail=(
                    "embedding_base_url is required when provider="
                    "'openai_compatible'"
                ),
            )
        if body.dimension is None and not (preset and preset.get("dimension")):
            raise HTTPException(
                status_code=400,
                detail=(
                    "dimension is required when provider='openai_compatible' "
                    "— set it to the output size of your endpoint's model"
                ),
            )

    api_key = (
        body.embedding_api_key
        or (preset["api_key"] if preset else None)
        or settings.embedding_api_key
    )
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"API key is required for the '{provider}' embedding provider",
        )
    base_url = body.embedding_base_url or (preset["base_url"] if preset else None)
    dimension_override = body.dimension or (preset["dimension"] if preset else None)

    try:
        from bigrag.services.embedding import get_embedding_model

        emb = get_embedding_model(
            provider=provider,
            model_name=model,
            dimension=dimension_override,
            api_key=api_key,
        )
        dimension = dimension_override or emb.dimension
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Create in Milvus first (idempotent — skips if exists)
    await vector_store.create_collection(body.name, dimension)

    import asyncpg

    try:
        row = await db.fetchrow(
            """
            INSERT INTO collections (name, description, embedding_provider, embedding_model,
                                      dimension, chunk_size, chunk_overlap, chunk_strategy,
                                      metadata,
                                      embedding_api_key, embedding_base_url,
                                      reranking_enabled, reranking_model, reranking_api_key,
                                      default_top_k, default_min_score, default_search_mode)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
            RETURNING *
            """,
            body.name,
            body.description,
            provider,
            model,
            dimension,
            body.chunk_size,
            body.chunk_overlap,
            body.chunk_strategy,
            body.metadata,
            api_key,
            base_url,
            body.reranking_enabled,
            body.reranking_model,
            body.reranking_api_key,
            body.default_top_k,
            body.default_min_score,
            body.default_search_mode,
        )
    except asyncpg.UniqueViolationError as e:
        raise HTTPException(status_code=409, detail="Collection already exists") from e
    except Exception:
        # Roll back Milvus collection if Postgres insert fails
        await vector_store.delete_collection(body.name)
        raise

    logger.info(
        f"create: collection={body.name} created provider={provider} model={model} dim={dimension}"
    )
    return _row_to_response(dict(row))


@router.get("/{name}", response_model=CollectionResponse)
async def get_collection(name: str, _: dict = Depends(get_current_user)):
    logger.info(f"get: collection={name}")
    row = await db.fetchrow("SELECT * FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")
    return _row_to_response(dict(row))


@router.get("/{name}/stats", response_model=CollectionStatsResponse)
async def get_collection_stats(name: str, _: dict = Depends(get_current_user)):
    logger.info(f"stats: collection={name}")
    row = await db.fetchrow("SELECT id FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")

    stats = await db.fetchrow(
        """
        SELECT
            COALESCE(SUM(chunk_count), 0) as total_chunks,
            COALESCE(SUM(token_count), 0) as total_tokens,
            COALESCE(SUM(file_size), 0) as total_size_bytes,
            COUNT(*) as document_count,
            COUNT(*) FILTER (WHERE status = 'ready') as ready,
            COUNT(*) FILTER (WHERE status = 'pending') as pending,
            COUNT(*) FILTER (WHERE status = 'processing') as processing,
            COUNT(*) FILTER (WHERE status = 'failed') as failed
        FROM documents WHERE collection_id = $1
        """,
        row["id"],
    )

    return CollectionStatsResponse(
        collection=name,
        document_count=stats["document_count"],
        total_chunks=int(stats["total_chunks"]),
        total_tokens=int(stats["total_tokens"]),
        total_size_bytes=int(stats["total_size_bytes"]),
        status_counts={
            "ready": stats["ready"],
            "pending": stats["pending"],
            "processing": stats["processing"],
            "failed": stats["failed"],
        },
    )


@router.put("/{name}", response_model=CollectionResponse)
async def update_collection(
    name: str, body: UpdateCollectionRequest, _: dict = Depends(get_current_user)
):
    logger.info(f"update: collection={name}")
    row = await db.fetchrow("SELECT * FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")

    from bigrag.database import build_update

    fields = {}
    if body.description is not None:
        fields["description"] = body.description
    if body.metadata is not None:
        fields["metadata"] = body.metadata
    if body.reranking_enabled is not None:
        fields["reranking_enabled"] = body.reranking_enabled
    if body.reranking_model is not None:
        fields["reranking_model"] = body.reranking_model
    if body.reranking_api_key is not None:
        fields["reranking_api_key"] = body.reranking_api_key
    if body.default_top_k is not None:
        fields["default_top_k"] = body.default_top_k
    if body.default_min_score is not None:
        fields["default_min_score"] = body.default_min_score
    if body.default_search_mode is not None:
        fields["default_search_mode"] = body.default_search_mode
    if not fields:
        return _row_to_response(dict(row))

    sql, params = build_update("collections", fields, "name", name)
    row = await db.fetchrow(sql, *params)
    from bigrag.routers import invalidate_collection_cache

    await invalidate_collection_cache(name)
    return _row_to_response(dict(row))


@router.delete("/{name}", response_model=StatusResponse)
async def delete_collection(name: str, _: dict = Depends(get_current_user)):
    logger.info(f"delete: collection={name}")
    row = await db.fetchrow("SELECT id FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")

    from bigrag.services.queue import ingestion_queue

    flushed = await ingestion_queue.flush_collection(name)
    logger.info(f"delete: flushed {flushed} queued jobs name={name}")

    await vector_store.delete_collection(name)
    logger.info(f"delete: milvus collection dropped name={name}")

    from bigrag.services.storage import get_storage

    deleted = await get_storage().delete_prefix(f"{name}/")
    logger.info(f"delete: storage files removed name={name} count={deleted}")

    # Delete from Postgres (cascades to documents)
    await db.execute("DELETE FROM collections WHERE name = $1", name)
    logger.info(f"delete: postgres records removed name={name}")

    from bigrag.routers import invalidate_collection_cache

    await invalidate_collection_cache(name)

    return {"status": "ok", "message": f"Collection '{name}' deleted"}


@router.get("/{name}/events")
async def collection_events_sse(name: str, _: dict = Depends(get_current_user)):
    """Stream real-time events for all activity in a collection via SSE."""
    from bigrag.services.event_bus import event_bus

    row = await db.fetchrow("SELECT id FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")

    import orjson

    async def generate():
        yield (
            f'data: {{"step":"connected","status":"connected",'
            f'"message":"Listening for events on {name}","progress":0}}\n\n'
        )

        key = f"collection:{name}"
        q = event_bus.subscribe(key)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                except TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                if event is None:
                    break
                data = {
                    "document_id": event.document_id,
                    "step": event.step,
                    "status": event.status,
                    "message": event.message,
                    "progress": event.progress,
                    **event.detail,
                }
                yield f"data: {orjson.dumps(data).decode()}\n\n"
        finally:
            event_bus.unsubscribe(key, q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{name}/truncate", response_model=StatusResponse)
async def truncate_collection(name: str, _: dict = Depends(get_current_user)):
    """Delete all documents, vectors, and storage files in a collection."""
    logger.info(f"truncate: collection={name}")
    row = await db.fetchrow("SELECT id FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")
    collection_id = row["id"]

    # Cancel running S3 ingest jobs (but keep the records)
    from bigrag.services.s3_ingest import cancel_job

    s3_jobs = await db.fetch(
        "SELECT id FROM s3_ingest_jobs WHERE collection_id = $1 "
        "AND status IN ('pending', 'listing', 'ingesting')",
        collection_id,
    )
    for j in s3_jobs:
        await cancel_job(str(j["id"]))
    logger.info(f"truncate: cancelled {len(s3_jobs)} running S3 jobs name={name}")

    # Flush queued ingestion jobs
    from bigrag.services.queue import ingestion_queue

    flushed = await ingestion_queue.flush_collection(name)
    logger.info(f"truncate: flushed {flushed} queued jobs name={name}")

    # Drop all vectors (collection gets recreated on next insert)
    await vector_store.delete_collection(name)
    logger.info(f"truncate: vectors cleared name={name}")

    # Delete storage files
    from bigrag.services.storage import get_storage

    deleted = await get_storage().delete_prefix(f"{name}/")
    logger.info(f"truncate: storage files removed name={name} count={deleted}")

    # Delete all documents
    await db.execute("DELETE FROM documents WHERE collection_id = $1", collection_id)
    await db.execute(
        "UPDATE collections SET document_count = 0, updated_at = now() WHERE id = $1",
        collection_id,
    )
    logger.info(f"truncate: documents removed name={name}")

    return {"status": "ok", "message": f"Collection '{name}' truncated"}
