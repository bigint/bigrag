from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from bigrag.config import settings
from bigrag.database import db
from bigrag.middleware.auth import get_current_user
from bigrag.models.collection import (
    CollectionListResponse,
    CollectionResponse,
    CollectionStatsResponse,
    CreateCollectionRequest,
    UpdateCollectionRequest,
)
from bigrag.services.vector_store import vector_store

logger = logging.getLogger("bigrag.routers.collections")

router = APIRouter(prefix="/v1/collections", tags=["collections"])


def _row_to_response(row: dict) -> CollectionResponse:
    data = {k: str(v) if isinstance(v, UUID) else v for k, v in row.items()}
    data["has_api_key"] = bool(data.pop("embedding_api_key", None))
    data.pop("embedding_base_url", None)  # unused DB column, hide from response
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

    provider = body.embedding_provider or settings.embedding_provider
    model = body.embedding_model or settings.embedding_model

    if provider not in ("openai", "cohere"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported embedding provider: '{provider}'. Supported: openai, cohere",
        )

    api_key = body.embedding_api_key or settings.embedding_api_key
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"API key is required for the '{provider}' embedding provider",
        )

    try:
        from bigrag.services.embedding import get_embedding_model

        emb = get_embedding_model(
            provider=provider,
            model_name=model,
            dimension=body.dimension,
            api_key=api_key,
        )
        dimension = body.dimension or emb.dimension
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create in Milvus first (idempotent — skips if exists)
    await vector_store.create_collection(body.name, dimension)

    import asyncpg

    try:
        row = await db.fetchrow(
            """
            INSERT INTO collections (name, description, embedding_provider, embedding_model,
                                      dimension, chunk_size, chunk_overlap, metadata,
                                      embedding_api_key,
                                      reranking_enabled, reranking_model, reranking_api_key,
                                      default_top_k, default_min_score, default_search_mode)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            RETURNING *
            """,
            body.name,
            body.description,
            provider,
            model,
            dimension,
            body.chunk_size,
            body.chunk_overlap,
            body.metadata,
            body.embedding_api_key,
            body.reranking_enabled,
            body.reranking_model,
            body.reranking_api_key,
            body.default_top_k,
            body.default_min_score,
            body.default_search_mode,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Collection already exists")
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

    invalidate_collection_cache(name)
    return _row_to_response(dict(row))


@router.delete("/{name}")
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

    invalidate_collection_cache(name)

    return {"status": "ok", "message": f"Collection '{name}' deleted"}
