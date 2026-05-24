from __future__ import annotations

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models.collection import (
    CollectionListResponse,
    CollectionResponse,
    CreateCollectionRequest,
)
from bigrag.routers.collections._router import router
from bigrag.routers.collections.serializers import collection_response
from bigrag.services import audit, collection_cache
from bigrag.services.collection_provision import create_vector_store_collection
from bigrag.services.collections import resolve_embedding_config
from bigrag.services.pagination import paginate
from bigrag.services.vector_store import vector_store
from bigrag.services.webhook import enqueue_webhook_event

logger = get_logger("bigrag.routers.collections")


@router.get("", response_model=CollectionListResponse)
async def list_collections(
    name: str | None = Query(default=None, description="Filter by name prefix"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0, le=10000),
    cursor: str | None = Query(default=None),
    include_total: bool = Query(default=False),
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    logger.info("list collections", name=name, limit=limit, offset=offset)
    stmt = sa.select(Collection).order_by(Collection.created_at.desc(), Collection.id.desc())
    count_stmt = sa.select(sa.func.count()).select_from(Collection)
    if name:
        stmt = stmt.where(Collection.name.ilike(f"{name}%"))
        count_stmt = count_stmt.where(Collection.name.ilike(f"{name}%"))

    result = await paginate(
        session,
        stmt,
        created_col=Collection.created_at,
        id_col=Collection.id,
        cursor=cursor,
        limit=limit,
        offset=offset,
        count_stmt=count_stmt if include_total else None,
    )

    logger.info("list collections complete", count=len(result.rows))
    return CollectionListResponse(
        collections=[collection_response(c) for c in result.rows],
        total=result.total,
        next_cursor=result.next_cursor,
    )


@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(
    body: CreateCollectionRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    logger.info(
        "create collection",
        name=body.name,
        provider=body.embedding_provider,
        model=body.embedding_model,
    )
    existing = await session.scalar(sa.select(Collection.id).where(Collection.name == body.name))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Collection already exists")

    config = await resolve_embedding_config(session, body)
    provider = config.provider
    model = config.model
    dimension = config.dimension
    preset = config.preset

    await create_vector_store_collection(body, dimension)

    collection = Collection(
        name=body.name,
        description=body.description,
        embedding_provider=provider,
        embedding_model=model,
        dimension=dimension,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        chunk_strategy=body.chunk_strategy,
        tenant_field=body.tenant_field,
        meta=body.metadata,
        metadata_schema=body.metadata_schema,
        embedding_api_key=None if preset else config.api_key,
        embedding_base_url=None if preset else config.base_url,
        embedding_preset_id=preset.id if preset else None,
        reranking_enabled=body.reranking_enabled,
        reranking_model=body.reranking_model,
        reranking_api_key=body.reranking_api_key,
        multimodal_enabled=body.multimodal_enabled,
        multimodal_enrichment_enabled=body.multimodal_enrichment_enabled,
        default_top_k=body.default_top_k,
        default_min_score=body.default_min_score,
        default_search_mode=body.default_search_mode,
    )
    session.add(collection)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        await vector_store.delete_collection(body.name)
        raise HTTPException(status_code=409, detail="Collection already exists") from e
    except Exception:
        await session.rollback()
        await vector_store.delete_collection(body.name)
        raise
    await session.refresh(collection)
    await collection_cache.invalidate(body.name)

    logger.info(
        "collection created",
        collection=body.name,
        provider=provider,
        model=model,
        dimension=dimension,
    )
    audit.record(
        request,
        user=user,
        action="collection.create",
        resource_type="collection",
        resource_id=str(collection.id),
        metadata={
            "name": body.name,
            "provider": provider,
            "model": model,
            "dimension": dimension,
        },
    )
    await enqueue_webhook_event(
        "collection.created",
        collection=collection.name,
        data={
            "collection_id": str(collection.id),
            "name": collection.name,
            "provider": provider,
            "model": model,
            "dimension": dimension,
        },
    )
    return collection_response(collection)
