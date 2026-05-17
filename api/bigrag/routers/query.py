from __future__ import annotations

import asyncio
import uuid

import orjson
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request

from bigrag.db.engine import session_factory
from bigrag.db.models import Document
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models.query import (
    AnalyticsResponse,
    BatchQueryItem,
    BatchQueryRequest,
    BatchQueryResponse,
    BatchQueryResultItem,
    EmbeddingModelInfo,
    EmbeddingModelListResponse,
    MultiQueryRequest,
    MultiQueryResponse,
    MultiQueryResult,
    QueryRequest,
    QueryResponse,
    QueryResult,
    QueryTimings,
    VectorDeleteRequest,
    VectorDeleteResponse,
    VectorUpsertRequest,
    VectorUpsertResponse,
)
from bigrag.routers import (
    ensure_embedding_or_400,
    get_collection_or_404,
    get_embedding_model_for,
    get_reranking_config,
)
from bigrag.services import access_log
from bigrag.services.embedding import AVAILABLE_MODELS
from bigrag.services.retrieval import invalidate_collection_query_cache, retrieve, retrieve_multi
from bigrag.services.runtime_settings import get_values
from bigrag.services.tenant_enforcement import require_tenant_filters, require_tenant_metadata
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.routers.query")

router = APIRouter(tags=["query"])


@router.post("/v1/collections/{collection_name}/query", response_model=QueryResponse)
async def query_collection(
    collection_name: str,
    body: QueryRequest,
    request: Request,
    _: dict = Depends(get_current_user),
):
    access_log.set_context(
        request,
        action="query.run",
        resource_type="collection",
        resource_id=collection_name,
        collection_name=collection_name,
        metadata={
            **access_log.query_fingerprint(body.query),
            **access_log.filter_summary(body.filters),
            "requested_top_k": body.top_k,
            "rerank_override": body.rerank,
        },
    )
    collection = await get_collection_or_404(collection_name)
    require_tenant_filters(collection, body.filters)
    logger.info(
        "query collection",
        collection=collection_name,
        query=body.query[:80],
        top_k=body.top_k,
        filters=body.filters,
    )

    embedding_model = ensure_embedding_or_400(collection)

    top_k = body.top_k or collection.get("default_top_k", 10)
    min_score = (
        body.min_score if body.min_score is not None else collection.get("default_min_score")
    )
    search_mode = body.search_mode or collection.get("default_search_mode", "semantic")
    access_log.set_context(
        request,
        resource_id=str(collection.get("id")),
        metadata={
            "top_k": top_k,
            "search_mode": search_mode,
            "min_score": min_score,
        },
    )

    outcome = await retrieve(
        collection_name=collection_name,
        query=body.query,
        embedding_model=embedding_model,
        top_k=top_k,
        filters=body.filters,
        min_score=min_score,
        search_mode=search_mode,
        reranking_config=get_reranking_config(collection),
        rerank_override=body.rerank,
        vector_store_provider=collection.get("vector_store_provider"),
    )

    logger.info(
        "query complete",
        collection=collection_name,
        results=len(outcome.results),
        total_ms=outcome.total_ms,
    )
    results = await _results_with_document_filenames(outcome.results)
    response = QueryResponse(
        results=[QueryResult(**_result_to_dict(r)) for r in results],
        query=body.query,
        collection=collection_name,
        total=len(outcome.results),
        timings=QueryTimings(
            embed_ms=outcome.embed_ms,
            search_ms=outcome.search_ms,
            rerank_ms=outcome.rerank_ms,
            cache_ms=outcome.cache_ms,
            total_ms=outcome.total_ms,
            cache_hit=outcome.cache_hit,
        ),
    )

    access_log.set_context(
        request,
        metadata={
            "result_count": response.total,
            "latency_ms": response.timings.total_ms if response.timings else None,
            "cache_hit": response.timings.cache_hit if response.timings else False,
            "avg_score": round(
                sum(result.score for result in response.results) / len(response.results),
                4,
            )
            if response.results
            else None,
        },
    )
    return response


def _result_to_dict(row: dict) -> dict:

    cleaned = {k: v for k, v in row.items() if k != "embedding"}
    metadata = cleaned.get("metadata") or {}
    for field_name in ("page_no", "char_start", "char_end", "document_filename"):
        if field_name in metadata and field_name not in cleaned:
            cleaned[field_name] = metadata[field_name]
    return cleaned


async def _results_with_document_filenames(rows: list[dict]) -> list[dict]:
    document_ids = []
    for row in rows:
        raw = row.get("document_id")
        if raw is None:
            continue
        try:
            document_ids.append(uuid.UUID(str(raw)))
        except ValueError:
            continue
    if not document_ids:
        return rows
    async with session_factory()() as session:
        records = await session.execute(
            sa.select(Document.id, Document.filename).where(Document.id.in_(set(document_ids)))
        )
        filenames = {str(document_id): filename for document_id, filename in records.all()}
    return [
        {
            **row,
            "document_filename": row.get("document_filename")
            or filenames.get(str(row.get("document_id"))),
        }
        for row in rows
    ]


@router.post("/v1/query", response_model=MultiQueryResponse)
async def multi_collection_query(
    body: MultiQueryRequest,
    request: Request,
    _: dict = Depends(get_current_user),
):
    access_log.set_context(
        request,
        action="query.multi",
        resource_type="collections",
        metadata={
            **access_log.query_fingerprint(body.query),
            **access_log.filter_summary(body.filters),
            "collections": body.collections,
            "collection_count": len(body.collections),
            "top_k": body.top_k,
            "search_mode": body.search_mode,
        },
    )
    logger.info(
        "multi-query",
        collections=body.collections,
        query=body.query[:80],
        top_k=body.top_k,
    )

    embedding_models = {}
    reranking_configs = {}
    vector_store_providers = {}
    resolved_collections = await asyncio.gather(
        *[get_collection_or_404(col_name) for col_name in body.collections]
    )
    for col_name, collection in zip(body.collections, resolved_collections, strict=True):
        require_tenant_filters(collection, body.filters)
        try:
            embedding_models[col_name] = get_embedding_model_for(collection)
        except (ImportError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Collection '{col_name}': {e}") from e
        reranking_configs[col_name] = get_reranking_config(collection)
        vector_store_providers[col_name] = collection.get("vector_store_provider") or "qdrant"

    results = await retrieve_multi(
        collection_names=body.collections,
        query=body.query,
        embedding_models=embedding_models,
        top_k=body.top_k,
        filters=body.filters,
        min_score=body.min_score,
        search_mode=body.search_mode,
        reranking_configs=reranking_configs,
        rerank_override=body.rerank,
        vector_store_providers=vector_store_providers,
    )

    logger.info("multi-query complete", collections=body.collections, results=len(results))
    access_log.set_context(
        request,
        metadata={
            "result_count": len(results),
            "collections_hit": sorted({str(row.get("collection")) for row in results}),
        },
    )
    results_with_filenames = await _results_with_document_filenames(results)
    return MultiQueryResponse(
        results=[MultiQueryResult(**_result_to_dict(r)) for r in results_with_filenames],
        query=body.query,
        collections=body.collections,
        total=len(results),
    )


@router.post("/v1/batch/query", response_model=BatchQueryResponse)
async def batch_query(
    body: BatchQueryRequest,
    request: Request,
    _: dict = Depends(get_current_user),
):
    access_log.set_context(
        request,
        action="query.batch",
        resource_type="collections",
        metadata={
            "batch_size": len(body.queries),
            "collections": sorted({item.collection for item in body.queries}),
            "query_hashes": [
                access_log.query_fingerprint(item.query)["query_hash"] for item in body.queries
            ],
        },
    )
    logger.info("batch-query", queries=len(body.queries))

    batch_semaphore = asyncio.Semaphore(8)

    async def run_one(item: BatchQueryItem) -> BatchQueryResultItem:
        async with batch_semaphore:
            collection = await get_collection_or_404(item.collection)
            require_tenant_filters(collection, item.filters)
            try:
                embedding_model = get_embedding_model_for(collection)
            except (ImportError, ValueError) as e:
                msg = f"Collection '{item.collection}': {e}"
                raise HTTPException(status_code=400, detail=msg) from e

            outcome = await retrieve(
                collection_name=item.collection,
                query=item.query,
                embedding_model=embedding_model,
                top_k=item.top_k,
                filters=item.filters,
                min_score=item.min_score,
                search_mode=item.search_mode,
                reranking_config=get_reranking_config(collection),
                rerank_override=item.rerank,
                vector_store_provider=collection.get("vector_store_provider"),
            )

            results = await _results_with_document_filenames(outcome.results)
            return BatchQueryResultItem(
                results=[QueryResult(**_result_to_dict(r)) for r in results],
                query=item.query,
                collection=item.collection,
                total=len(outcome.results),
            )

    results = await asyncio.gather(*[run_one(item) for item in body.queries])
    access_log.set_context(
        request,
        metadata={
            "result_count": sum(item.total for item in results),
            "completed_queries": len(results),
        },
    )

    return BatchQueryResponse(results=list(results))


@router.post(
    "/v1/collections/{collection_name}/vectors/upsert",
    response_model=VectorUpsertResponse,
)
async def upsert_vectors(
    collection_name: str,
    body: VectorUpsertRequest,
    request: Request,
    _: dict = Depends(get_current_user),
):
    access_log.set_context(
        request,
        action="vectors.upsert",
        resource_type="collection",
        resource_id=collection_name,
        collection_name=collection_name,
        metadata={"vector_count": len(body.vectors)},
    )
    collection = await get_collection_or_404(collection_name)
    limits = await get_values(
        [
            "max_vector_upsert_count",
            "max_vector_text_chars",
            "max_vector_metadata_bytes",
        ]
    )
    if len(body.vectors) > limits["max_vector_upsert_count"]:
        raise HTTPException(
            status_code=413,
            detail=f"Too many vectors. Max: {limits['max_vector_upsert_count']}",
        )
    logger.info("vector upsert", collection=collection_name, vectors=len(body.vectors))

    ids = [v.id for v in body.vectors]
    embeddings = [v.embedding for v in body.vectors]
    texts = [v.text for v in body.vectors]
    metadata = [v.metadata for v in body.vectors]
    expected_dimension = int(collection.get("dimension") or 0)
    for index, vector in enumerate(body.vectors):
        if expected_dimension and len(vector.embedding) != expected_dimension:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"vectors[{index}].embedding has dimension {len(vector.embedding)}, "
                    f"expected {expected_dimension}"
                ),
            )
        if len(vector.text) > limits["max_vector_text_chars"]:
            raise HTTPException(
                status_code=413,
                detail=f"vectors[{index}].text is too large",
            )
        metadata_bytes = len(orjson.dumps(vector.metadata))
        if metadata_bytes > limits["max_vector_metadata_bytes"]:
            raise HTTPException(
                status_code=413,
                detail=f"vectors[{index}].metadata is too large",
            )
    for index, meta in enumerate(metadata):
        require_tenant_metadata(collection, meta, label=f"vectors[{index}].metadata")

    count = await vector_store.upsert(
        collection=collection_name,
        ids=ids,
        embeddings=embeddings,
        texts=texts,
        metadata=metadata,
        provider=collection.get("vector_store_provider"),
    )
    await invalidate_collection_query_cache(collection_name)
    logger.info("vector upsert complete", collection=collection_name, upserted=count)
    access_log.set_context(request, metadata={"upserted": count})

    return VectorUpsertResponse(upserted=count)


@router.post(
    "/v1/collections/{collection_name}/vectors/delete",
    response_model=VectorDeleteResponse,
)
async def delete_vectors(
    collection_name: str,
    body: VectorDeleteRequest,
    request: Request,
    _: dict = Depends(get_current_user),
):
    access_log.set_context(
        request,
        action="vectors.delete",
        resource_type="collection",
        resource_id=collection_name,
        collection_name=collection_name,
        metadata={"vector_count": len(body.ids)},
    )
    limits = await get_values(["max_vector_delete_count"])
    if len(body.ids) > limits["max_vector_delete_count"]:
        raise HTTPException(
            status_code=413,
            detail=f"Too many vector IDs. Max: {limits['max_vector_delete_count']}",
        )
    collection = await get_collection_or_404(collection_name)
    logger.info("vector delete", collection=collection_name, ids=len(body.ids))
    await vector_store.delete_by_ids(
        collection_name,
        body.ids,
        provider=collection.get("vector_store_provider"),
    )
    await invalidate_collection_query_cache(collection_name)
    access_log.set_context(request, metadata={"deleted": len(body.ids)})
    return VectorDeleteResponse(deleted=len(body.ids))


@router.get("/v1/collections/{collection_name}/analytics", response_model=AnalyticsResponse)
async def collection_analytics(
    collection_name: str,
    request: Request,
    _: dict = Depends(get_current_user),
):
    access_log.set_context(
        request,
        action="analytics.read",
        resource_type="collection",
        resource_id=collection_name,
        collection_name=collection_name,
    )
    await get_collection_or_404(collection_name)

    from bigrag.services.analytics import collection_analytics as analytics_for

    return AnalyticsResponse(**await analytics_for(collection_name))


@router.get("/v1/embeddings/models", response_model=EmbeddingModelListResponse)
async def list_embedding_models(
    _: dict = Depends(get_current_user),
) -> EmbeddingModelListResponse:
    return EmbeddingModelListResponse(models=[EmbeddingModelInfo(**m) for m in AVAILABLE_MODELS])
