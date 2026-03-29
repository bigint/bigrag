from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from bigrag.config import settings
from bigrag.database import db
from bigrag.middleware.auth import get_current_user
from bigrag.models.collection import (
    CollectionListResponse,
    CollectionResponse,
    CreateCollectionRequest,
    UpdateCollectionRequest,
)
from bigrag.services.vector_store import vector_store

router = APIRouter(prefix="/v1/collections", tags=["collections"])


def _row_to_response(row: dict) -> CollectionResponse:
    data = {k: str(v) if isinstance(v, UUID) else v for k, v in row.items()}
    data["has_api_key"] = bool(data.pop("embedding_api_key", None))
    data.pop("embedding_base_url", None)
    return CollectionResponse(**data)


@router.get("", response_model=CollectionListResponse)
async def list_collections(_: dict = Depends(get_current_user)):
    rows = await db.fetch("SELECT * FROM collections ORDER BY created_at DESC")
    return CollectionListResponse(
        collections=[_row_to_response(dict(r)) for r in rows]
    )


@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(body: CreateCollectionRequest, _: dict = Depends(get_current_user)):
    # Check if collection already exists
    existing = await db.fetchrow("SELECT id FROM collections WHERE name = $1", body.name)
    if existing:
        raise HTTPException(status_code=409, detail="Collection already exists")

    provider = body.embedding_provider or settings.embedding_provider
    model = body.embedding_model or settings.embedding_model
    dimension = body.dimension or settings.embedding_dimension

    # Providers that require an API key
    api_key = body.embedding_api_key or settings.embedding_api_key
    base_url = body.embedding_base_url or settings.embedding_base_url

    if provider in ("openai", "cohere", "custom") and not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"API key is required for the '{provider}' embedding provider",
        )
    if provider in ("ollama", "custom") and not base_url:
        raise HTTPException(
            status_code=400,
            detail=f"Base URL is required for the '{provider}' embedding provider",
        )

    # Validate the embedding provider is available
    try:
        from bigrag.services.embedding import get_embedding_model
        get_embedding_model(
            provider=provider, model_name=model, dimension=dimension,
            api_key=api_key, base_url=base_url,
        )
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
                                      embedding_api_key, embedding_base_url)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
            """,
            body.name, body.description, provider, model,
            dimension, body.chunk_size, body.chunk_overlap, body.metadata,
            body.embedding_api_key, body.embedding_base_url,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Collection already exists")
    except Exception:
        # Roll back Milvus collection if Postgres insert fails
        await vector_store.delete_collection(body.name)
        raise

    return _row_to_response(dict(row))


@router.get("/{name}", response_model=CollectionResponse)
async def get_collection(name: str, _: dict = Depends(get_current_user)):
    row = await db.fetchrow("SELECT * FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")
    return _row_to_response(dict(row))


@router.put("/{name}", response_model=CollectionResponse)
async def update_collection(
    name: str, body: UpdateCollectionRequest, _: dict = Depends(get_current_user)
):
    row = await db.fetchrow("SELECT * FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")

    updates = []
    params = []
    idx = 1

    if body.description is not None:
        updates.append(f"description = ${idx}")
        params.append(body.description)
        idx += 1
    if body.metadata is not None:
        updates.append(f"metadata = ${idx}")
        params.append(body.metadata)
        idx += 1

    if not updates:
        return _row_to_response(dict(row))

    updates.append("updated_at = now()")
    params.append(name)

    row = await db.fetchrow(
        f"UPDATE collections SET {', '.join(updates)} WHERE name = ${idx} RETURNING *",
        *params,
    )
    return _row_to_response(dict(row))


@router.delete("/{name}")
async def delete_collection(name: str, _: dict = Depends(get_current_user)):
    row = await db.fetchrow("SELECT id FROM collections WHERE name = $1", name)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Delete from Milvus
    await vector_store.delete_collection(name)

    # Delete uploaded files from disk
    upload_dir = Path(settings.upload_dir) / name
    if upload_dir.exists():
        import shutil
        shutil.rmtree(upload_dir, ignore_errors=True)

    # Delete from Postgres (cascades to documents)
    await db.execute("DELETE FROM collections WHERE name = $1", name)

    return {"status": "ok", "message": f"Collection '{name}' deleted"}
