from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection, Document, EmbeddingPreset
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models import StatusResponse
from bigrag.models.collection import (
    CollectionListResponse,
    CollectionResponse,
    CollectionStatsResponse,
    CreateCollectionRequest,
    UpdateCollectionRequest,
)
from bigrag.routers import enforce_collection_pin
from bigrag.services import audit, collection_cache
from bigrag.services.collection_provision import (
    create_vector_store_collection,
    verify_embedding_credentials,
)
from bigrag.services.collections import (
    delete_collection as service_delete_collection,
)
from bigrag.services.collections import (
    truncate_collection as service_truncate_collection,
)
from bigrag.services.error_sanitize import safe_error_detail
from bigrag.services.pagination import apply_cursor, build_response_cursor, decode_cursor_or_400
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.runtime_settings import get_values
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.routers.collections")

router = APIRouter(prefix="/v1/collections", tags=["collections"])


def _collection_response(c: Collection) -> CollectionResponse:
    return CollectionResponse(
        id=str(c.id),
        name=c.name,
        description=c.description,
        embedding_provider=c.embedding_provider,
        embedding_model=c.embedding_model,
        vector_store_provider=c.vector_store_provider,
        dimension=c.dimension,
        chunk_size=c.chunk_size,
        chunk_overlap=c.chunk_overlap,
        chunk_strategy=c.chunk_strategy,
        index_type=c.index_type,
        tenant_field=c.tenant_field,
        has_metadata_schema=bool(c.metadata_schema),
        document_count=c.document_count,
        has_api_key=bool(c.embedding_api_key) or c.embedding_preset_id is not None,
        embedding_preset_id=str(c.embedding_preset_id) if c.embedding_preset_id else None,
        reranking_enabled=c.reranking_enabled,
        reranking_model=c.reranking_model,
        has_reranking_api_key=bool(c.reranking_api_key),
        multimodal_enabled=c.multimodal_enabled,
        multimodal_enrichment_enabled=c.multimodal_enrichment_enabled,
        default_top_k=c.default_top_k,
        default_min_score=c.default_min_score,
        default_search_mode=c.default_search_mode,
        metadata=c.meta or {},
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("", response_model=CollectionListResponse)
async def list_collections(
    name: str | None = Query(default=None, description="Filter by name prefix"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
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

    cursor_tuple = decode_cursor_or_400(cursor)

    if cursor_tuple is not None:
        stmt = apply_cursor(stmt, Collection.created_at, Collection.id, cursor_tuple).limit(
            limit + 1
        )
    else:
        stmt = stmt.limit(limit + 1).offset(offset)

    rows = (await session.scalars(stmt)).all()
    page, next_cursor = build_response_cursor(list(rows), "created_at", "id", limit)

    total: int | None = None
    if include_total:
        total = (await session.scalar(count_stmt)) or 0

    logger.info("list collections complete", count=len(page))
    return CollectionListResponse(
        collections=[_collection_response(c) for c in page],
        total=total,
        next_cursor=next_cursor,
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
        vector_store_provider=body.vector_store_provider,
        provider=body.embedding_provider,
        model=body.embedding_model,
    )
    existing = await session.scalar(sa.select(Collection.id).where(Collection.name == body.name))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Collection already exists")

    preset: EmbeddingPreset | None = None
    if body.embedding_preset_id:
        try:
            preset_uuid = UUID(body.embedding_preset_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid embedding_preset_id") from e
        preset = await session.get(EmbeddingPreset, preset_uuid)
        if preset is None:
            raise HTTPException(status_code=400, detail="Embedding preset not found")

    defaults = await get_values(
        [
            "embedding_provider",
            "embedding_model",
            "embedding_dimension",
            "embedding_base_url",
            "embedding_api_key",
        ]
    )
    provider = (
        body.embedding_provider
        or (preset.provider if preset else None)
        or defaults["embedding_provider"]
    )
    model = (
        body.embedding_model or (preset.model if preset else None) or defaults["embedding_model"]
    )

    if provider not in ("openai", "openai_compatible", "cohere", "voyage"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported embedding provider: '{provider}'. "
                f"Supported: openai, openai_compatible, cohere, voyage"
            ),
        )
    if provider == "openai_compatible":
        has_base_url = bool(
            body.embedding_base_url
            or (preset and preset.base_url)
            or defaults["embedding_base_url"]
        )
        if not has_base_url:
            raise HTTPException(
                status_code=400,
                detail=("embedding_base_url is required when provider='openai_compatible'"),
            )
        if body.dimension is None and not (preset and preset.dimension):
            raise HTTPException(
                status_code=400,
                detail=(
                    "dimension is required when provider='openai_compatible' "
                    "— set it to the output size of your endpoint's model"
                ),
            )

    api_key = (
        body.embedding_api_key
        or (preset.api_key if preset else None)
        or defaults["embedding_api_key"]
    )
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"API key is required for the '{provider}' embedding provider",
        )
    base_url = (
        body.embedding_base_url
        or (preset.base_url if preset else None)
        or defaults["embedding_base_url"]
    )
    dimension_override = (
        body.dimension or (preset.dimension if preset else None) or defaults["embedding_dimension"]
    )

    await verify_embedding_credentials(provider, api_key, base_url, model)
    try:
        from bigrag.services.embedding import get_embedding_model

        emb = get_embedding_model(
            provider=provider,
            model_name=model,
            dimension=dimension_override,
            api_key=api_key,
            base_url=base_url,
        )
        dimension = dimension_override or emb.dimension
    except (ImportError, ValueError) as e:
        logger.warning("embedding model unavailable", error=repr(e))
        raise HTTPException(
            status_code=400,
            detail=safe_error_detail(e, "Embedding provider is not available."),
        ) from e

    await create_vector_store_collection(body, dimension)

    collection = Collection(
        name=body.name,
        description=body.description,
        vector_store_provider=body.vector_store_provider,
        embedding_provider=provider,
        embedding_model=model,
        dimension=dimension,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        chunk_strategy=body.chunk_strategy,
        index_type=body.index_type,
        tenant_field=body.tenant_field,
        meta=body.metadata,
        metadata_schema=body.metadata_schema,
        embedding_api_key=None if preset else api_key,
        embedding_base_url=None if preset else base_url,
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
        await vector_store.delete_collection(body.name, provider=body.vector_store_provider)
        raise HTTPException(status_code=409, detail="Collection already exists") from e
    except Exception:
        await session.rollback()
        await vector_store.delete_collection(body.name, provider=body.vector_store_provider)
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
            "vector_store_provider": body.vector_store_provider,
            "model": model,
            "dimension": dimension,
        },
    )
    return _collection_response(collection)


@router.get("/{name}", response_model=CollectionResponse)
async def get_collection(
    name: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, name)
    logger.info("get collection", collection=name)
    collection = await session.scalar(sa.select(Collection).where(Collection.name == name))
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return _collection_response(collection)


@router.get("/{name}/stats", response_model=CollectionStatsResponse)
async def get_collection_stats(
    name: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, name)
    logger.info("collection stats", collection=name)
    collection_id = await session.scalar(sa.select(Collection.id).where(Collection.name == name))
    if collection_id is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    stats = (
        await session.execute(
            sa.select(
                sa.func.coalesce(sa.func.sum(Document.chunk_count), 0).label("total_chunks"),
                sa.func.coalesce(sa.func.sum(Document.token_count), 0).label("total_tokens"),
                sa.func.coalesce(sa.func.sum(Document.file_size), 0).label("total_size"),
                sa.func.count().label("document_count"),
                sa.func.count().filter(Document.status == "ready").label("ready"),
                sa.func.count().filter(Document.status == "pending").label("pending"),
                sa.func.count().filter(Document.status == "processing").label("processing"),
                sa.func.count().filter(Document.status == "failed").label("failed"),
            ).where(Document.collection_id == collection_id)
        )
    ).one()

    return CollectionStatsResponse(
        collection=name,
        document_count=stats.document_count,
        total_chunks=int(stats.total_chunks),
        total_tokens=int(stats.total_tokens),
        total_size_bytes=int(stats.total_size),
        status_counts={
            "ready": stats.ready,
            "pending": stats.pending,
            "processing": stats.processing,
            "failed": stats.failed,
        },
    )


@router.put("/{name}", response_model=CollectionResponse)
async def update_collection(
    name: str,
    body: UpdateCollectionRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, name)
    logger.info("update collection", collection=name)
    collection = await session.scalar(sa.select(Collection).where(Collection.name == name))
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    fields: list[str] = []
    if body.description is not None:
        collection.description = body.description
        fields.append("description")
    if body.metadata is not None:
        collection.meta = body.metadata
        fields.append("metadata")
    if "embedding_api_key" in body.model_fields_set:
        if body.embedding_api_key is None:
            collection.embedding_api_key = None
        else:
            new_key = body.embedding_api_key.strip()
            if not new_key:
                raise HTTPException(
                    status_code=422,
                    detail="embedding_api_key cannot be empty.",
                )
            await verify_embedding_credentials(
                collection.embedding_provider,
                new_key,
                collection.embedding_base_url,
                collection.embedding_model,
            )
            collection.embedding_api_key = new_key
        if body.embedding_api_key is not None and collection.embedding_preset_id is not None:
            collection.embedding_preset_id = None
            fields.append("embedding_preset_id")
        fields.append("embedding_api_key")
    if body.reranking_enabled is not None:
        collection.reranking_enabled = body.reranking_enabled
        fields.append("reranking_enabled")
    if body.reranking_model is not None:
        collection.reranking_model = body.reranking_model
        fields.append("reranking_model")
    if "reranking_api_key" in body.model_fields_set:
        collection.reranking_api_key = body.reranking_api_key
        fields.append("reranking_api_key")
    if body.multimodal_enabled is not None:
        collection.multimodal_enabled = body.multimodal_enabled
        fields.append("multimodal_enabled")
        if not body.multimodal_enabled and collection.multimodal_enrichment_enabled:
            collection.multimodal_enrichment_enabled = False
            fields.append("multimodal_enrichment_enabled")
    if body.multimodal_enrichment_enabled is not None:
        if body.multimodal_enrichment_enabled and not collection.multimodal_enabled:
            collection.multimodal_enabled = True
            fields.append("multimodal_enabled")
        collection.multimodal_enrichment_enabled = body.multimodal_enrichment_enabled
        fields.append("multimodal_enrichment_enabled")
    if body.default_top_k is not None:
        collection.default_top_k = body.default_top_k
        fields.append("default_top_k")
    if body.default_min_score is not None:
        collection.default_min_score = body.default_min_score
        fields.append("default_min_score")
    if body.default_search_mode is not None:
        collection.default_search_mode = body.default_search_mode
        fields.append("default_search_mode")
    if body.chunk_strategy is not None:
        collection.chunk_strategy = body.chunk_strategy
        fields.append("chunk_strategy")
    if body.metadata_schema is not None:
        collection.metadata_schema = body.metadata_schema
        fields.append("metadata_schema")

    await session.commit()
    await session.refresh(collection)
    await collection_cache.invalidate(name)
    await invalidate_collection_query_cache(name)

    audit.record(
        request,
        user=user,
        action="collection.update",
        resource_type="collection",
        resource_id=str(collection.id),
        metadata={"name": name, "fields": fields},
    )
    return _collection_response(collection)


@router.delete("/{name}", response_model=StatusResponse)
async def delete_collection(
    name: str,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, name)
    deleted_id = await service_delete_collection(session, name)
    audit.record(
        request,
        user=user,
        action="collection.delete",
        resource_type="collection",
        resource_id=deleted_id,
        metadata={"name": name},
    )
    return StatusResponse(status="ok", message=f"Collection '{name}' deleted")


@router.post("/{name}/truncate", response_model=StatusResponse)
async def truncate_collection(
    name: str,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    enforce_collection_pin(user, name)
    collection_id = await service_truncate_collection(session, name)
    audit.record(
        request,
        user=user,
        action="collection.truncate",
        resource_type="collection",
        resource_id=collection_id,
        metadata={"name": name},
    )
    return StatusResponse(status="ok", message=f"Collection '{name}' truncated")
