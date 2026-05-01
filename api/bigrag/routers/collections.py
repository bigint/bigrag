from __future__ import annotations

import asyncio
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from bigrag.config import settings
from bigrag.db.models import Collection, Document, EmbeddingPreset
from bigrag.db.session import get_session
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
from bigrag.services import audit, semantic_cache
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
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
        dimension=c.dimension,
        chunk_size=c.chunk_size,
        chunk_overlap=c.chunk_overlap,
        chunk_strategy=c.chunk_strategy,
        index_type=c.index_type,
        tenant_field=c.tenant_field,
        has_metadata_schema=bool(c.metadata_schema),
        document_count=c.document_count,
        has_api_key=bool(c.embedding_api_key),
        reranking_enabled=c.reranking_enabled,
        reranking_model=c.reranking_model,
        has_reranking_api_key=bool(c.reranking_api_key),
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
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    logger.info(f"list: fetching collections name={name} limit={limit} offset={offset}")
    stmt = sa.select(Collection).order_by(Collection.created_at.desc())
    count_stmt = sa.select(sa.func.count()).select_from(Collection)
    if name:
        stmt = stmt.where(Collection.name.ilike(f"{name}%"))
        count_stmt = count_stmt.where(Collection.name.ilike(f"{name}%"))

    rows = (await session.scalars(stmt.limit(limit).offset(offset))).all()
    total = await session.scalar(count_stmt)

    logger.info(f"list: found {len(rows)} collections")
    return CollectionListResponse(
        collections=[_collection_response(c) for c in rows],
        total=total or 0,
    )


@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(
    body: CreateCollectionRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    logger.info(
        f"create: name={body.name} provider={body.embedding_provider} model={body.embedding_model}"
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

    provider = (
        body.embedding_provider
        or (preset.provider if preset else None)
        or settings.embedding_provider
    )
    model = body.embedding_model or (preset.model if preset else None) or settings.embedding_model

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
            body.embedding_base_url or (preset and preset.base_url) or settings.embedding_base_url
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
        body.embedding_api_key or (preset.api_key if preset else None) or settings.embedding_api_key
    )
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"API key is required for the '{provider}' embedding provider",
        )
    base_url = (
        body.embedding_base_url
        or (preset.base_url if preset else None)
        or settings.embedding_base_url
    )
    dimension_override = body.dimension or (preset.dimension if preset else None)

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
        raise HTTPException(status_code=400, detail=str(e)) from e

    await vector_store.create_collection(
        body.name,
        dimension,
        index_type=body.index_type,
        tenant_field=body.tenant_field,
    )

    collection = Collection(
        name=body.name,
        description=body.description,
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
        embedding_api_key=api_key,
        embedding_base_url=base_url,
        reranking_enabled=body.reranking_enabled,
        reranking_model=body.reranking_model,
        reranking_api_key=body.reranking_api_key,
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

    logger.info(
        f"create: collection={body.name} created provider={provider} model={model} dim={dimension}"
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
    return _collection_response(collection)


@router.post("/{name}/reembed", response_model=StatusResponse)
async def reembed_collection(
    name: str,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> StatusResponse:

    collection = await session.scalar(sa.select(Collection).where(Collection.name == name))
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    docs = (
        await session.execute(
            sa.select(Document.id, Document.file_path)
            .where(Document.collection_id == collection.id)
            .where(Document.status.in_(("ready", "failed")))
        )
    ).all()

    collection_dict = {
        "embedding_provider": collection.embedding_provider,
        "embedding_model": collection.embedding_model,
        "embedding_api_key": collection.embedding_api_key,
        "embedding_base_url": collection.embedding_base_url,
        "dimension": collection.dimension,
        "chunk_size": collection.chunk_size,
        "chunk_overlap": collection.chunk_overlap,
        "chunk_strategy": collection.chunk_strategy or "paragraph",
        "tenant_field": collection.tenant_field,
    }
    jobs = [
        create_ingestion_job(
            document_id=str(doc_id),
            file_path=file_path,
            collection_name=name,
            collection=collection_dict,
            fallback_api_key=settings.embedding_api_key,
        )
        for doc_id, file_path in docs
    ]

    for doc_id, _file_path in docs:
        await session.execute(
            sa.update(Document)
            .where(Document.id == doc_id)
            .values(status="pending", error_message=None)
        )
    await session.commit()

    for job in jobs:
        await ingestion_queue.enqueue(job)

    await semantic_cache.invalidate(name)
    logger.info("reembed: queued", collection=name, docs=len(docs))
    audit.record(
        request,
        user=user,
        action="collection.reembed",
        resource_type="collection",
        resource_id=str(collection.id),
        metadata={"name": name, "docs_queued": len(docs)},
    )
    return StatusResponse(
        status="ok",
        message=f"Queued {len(docs)} documents for re-embedding",
    )


@router.get("/{name}", response_model=CollectionResponse)
async def get_collection(
    name: str,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    logger.info(f"get: collection={name}")
    collection = await session.scalar(sa.select(Collection).where(Collection.name == name))
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return _collection_response(collection)


@router.get("/{name}/stats", response_model=CollectionStatsResponse)
async def get_collection_stats(
    name: str,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    logger.info(f"stats: collection={name}")
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
    logger.info(f"update: collection={name}")
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
    if body.reranking_enabled is not None:
        collection.reranking_enabled = body.reranking_enabled
        fields.append("reranking_enabled")
    if body.reranking_model is not None:
        collection.reranking_model = body.reranking_model
        fields.append("reranking_model")
    if body.reranking_api_key is not None:
        collection.reranking_api_key = body.reranking_api_key
        fields.append("reranking_api_key")
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

    from bigrag.routers import invalidate_collection_cache

    await invalidate_collection_cache(name)
    await semantic_cache.invalidate(name)
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
    logger.info(f"delete: collection={name}")
    collection = await session.scalar(sa.select(Collection).where(Collection.name == name))
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    flushed = await ingestion_queue.cancel_collection(name)
    logger.info(f"delete: cancelled/flushed {flushed} queued jobs name={name}")

    await vector_store.delete_collection(name)
    logger.info(f"delete: qdrant collection dropped name={name}")

    from bigrag.services.storage import get_storage

    deleted = await get_storage().delete_prefix(f"{name}/")
    logger.info(f"delete: storage files removed name={name} count={deleted}")

    deleted_id = str(collection.id)
    await session.delete(collection)
    await session.commit()
    logger.info(f"delete: postgres records removed name={name}")

    from bigrag.routers import invalidate_collection_cache

    await invalidate_collection_cache(name)
    await semantic_cache.invalidate(name)
    audit.record(
        request,
        user=user,
        action="collection.delete",
        resource_type="collection",
        resource_id=deleted_id,
        metadata={"name": name},
    )

    return StatusResponse(status="ok", message=f"Collection '{name}' deleted")


@router.get("/{name}/events")
async def collection_events_sse(
    name: str,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):

    from bigrag.services.event_bus import event_bus

    exists = await session.scalar(sa.select(Collection.id).where(Collection.name == name))
    if exists is None:
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
async def truncate_collection(
    name: str,
    request: Request,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):

    logger.info(f"truncate: collection={name}")
    collection_id = await session.scalar(sa.select(Collection.id).where(Collection.name == name))
    if collection_id is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    flushed = await ingestion_queue.cancel_collection(name)
    logger.info(f"truncate: cancelled/flushed {flushed} queued jobs name={name}")

    await vector_store.delete_collection(name)
    logger.info(f"truncate: vectors cleared name={name}")

    from bigrag.services.storage import get_storage

    deleted = await get_storage().delete_prefix(f"{name}/")
    logger.info(f"truncate: storage files removed name={name} count={deleted}")

    await session.execute(sa.delete(Document).where(Document.collection_id == collection_id))
    await session.execute(
        sa.update(Collection).where(Collection.id == collection_id).values(document_count=0)
    )
    await session.commit()
    logger.info(f"truncate: documents removed name={name}")
    await semantic_cache.invalidate(name)

    audit.record(
        request,
        user=user,
        action="collection.truncate",
        resource_type="collection",
        resource_id=str(collection_id),
        metadata={"name": name},
    )
    return StatusResponse(status="ok", message=f"Collection '{name}' truncated")
