from __future__ import annotations

import asyncio
import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request

from bigrag.db.engine import session_factory
from bigrag.db.models import Document
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models.query import (
    BatchQueryItem,
    BatchQueryRequest,
    BatchQueryResponse,
    BatchQueryResultItem,
    MultiQueryRequest,
    MultiQueryResponse,
    MultiQueryResult,
    QueryRequest,
    QueryResponse,
    QueryResult,
    QueryTimings,
)
from bigrag.routers import (
    ensure_embedding_or_400,
    get_collection_or_404,
    get_embedding_model_for,
    get_reranking_config,
)
from bigrag.services import access_log
from bigrag.services.retrieval import retrieve, retrieve_multi
from bigrag.services.tenant_enforcement import require_tenant_filters

logger = get_logger("bigrag.routers.query")

router = APIRouter(tags=["query"])

_FANOUT_LIMIT = 8


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
            "skip_cache": body.skip_cache,
        },
    )
    collection = await get_collection_or_404(collection_name)
    require_tenant_filters(collection, body.filters)
    logger.debug(
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
        skip_cache=body.skip_cache,
    )

    logger.debug(
        "query complete",
        collection=collection_name,
        results=len(outcome.results),
        total_ms=outcome.total_ms,
    )
    results = await _results_with_document_filenames(outcome.results)
    include_multimodal = bool(body.multimodal and collection.get("multimodal_enabled"))
    response = QueryResponse(
        results=[
            QueryResult(**_result_to_dict(r, include_multimodal=include_multimodal))
            for r in results
        ],
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


def _result_to_dict(row: dict, *, include_multimodal: bool) -> dict:

    cleaned = {k: v for k, v in row.items() if k != "embedding"}
    metadata = cleaned.get("metadata") or {}
    for field_name in ("page_no", "char_start", "char_end", "document_filename"):
        if field_name in metadata and field_name not in cleaned:
            cleaned[field_name] = metadata[field_name]
    if (
        include_multimodal
        and "multimodal_elements" in metadata
        and "multimodal_elements" not in cleaned
    ):
        cleaned["multimodal_elements"] = metadata["multimodal_elements"]
    if not include_multimodal and isinstance(metadata, dict):
        cleaned["metadata"] = {k: v for k, v in metadata.items() if k != "multimodal_elements"}
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
            "skip_cache": body.skip_cache,
        },
    )
    logger.debug(
        "multi-query",
        collections=body.collections,
        query=body.query[:80],
        top_k=body.top_k,
    )

    embedding_models = {}
    reranking_configs = {}
    resolve_semaphore = asyncio.Semaphore(_FANOUT_LIMIT)

    async def _resolve(col_name: str):
        async with resolve_semaphore:
            return await get_collection_or_404(col_name)

    resolved_collections = await asyncio.gather(
        *[_resolve(col_name) for col_name in body.collections]
    )
    for col_name, collection in zip(body.collections, resolved_collections, strict=True):
        require_tenant_filters(collection, body.filters)
        try:
            embedding_models[col_name] = get_embedding_model_for(collection)
        except (ImportError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Collection '{col_name}': {e}") from e
        reranking_configs[col_name] = get_reranking_config(collection)
    include_multimodal_by_collection = {
        col_name: bool(body.multimodal and collection.get("multimodal_enabled"))
        for col_name, collection in zip(body.collections, resolved_collections, strict=True)
    }

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
        skip_cache=body.skip_cache,
    )

    logger.debug("multi-query complete", collections=body.collections, results=len(results))
    access_log.set_context(
        request,
        metadata={
            "result_count": len(results),
            "collections_hit": sorted({str(row.get("collection")) for row in results}),
        },
    )
    results_with_filenames = await _results_with_document_filenames(results)
    return MultiQueryResponse(
        results=[
            MultiQueryResult(
                **_result_to_dict(
                    r,
                    include_multimodal=include_multimodal_by_collection.get(
                        str(r.get("collection")),
                        False,
                    ),
                )
            )
            for r in results_with_filenames
        ],
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
            "skip_cache_count": sum(1 for item in body.queries if item.skip_cache),
        },
    )
    logger.debug("batch-query", queries=len(body.queries))

    batch_semaphore = asyncio.Semaphore(_FANOUT_LIMIT)

    async def run_one(item: BatchQueryItem) -> tuple[BatchQueryItem, list[dict], int, bool]:
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
                skip_cache=item.skip_cache,
            )

            include_multimodal = bool(item.multimodal and collection.get("multimodal_enabled"))
            return item, outcome.results, len(outcome.results), include_multimodal

    raw_results = await asyncio.gather(*[run_one(item) for item in body.queries])
    flat_rows = []
    row_counts = []
    for _, rows, _, _ in raw_results:
        row_counts.append(len(rows))
        flat_rows.extend(rows)
    enriched_rows = await _results_with_document_filenames(flat_rows)
    results = []
    cursor = 0
    for (item, _, total, include_multimodal), row_count in zip(
        raw_results,
        row_counts,
        strict=True,
    ):
        rows = enriched_rows[cursor : cursor + row_count]
        cursor += row_count
        results.append(
            BatchQueryResultItem(
                results=[
                    QueryResult(**_result_to_dict(r, include_multimodal=include_multimodal))
                    for r in rows
                ],
                query=item.query,
                collection=item.collection,
                total=total,
            )
        )
    access_log.set_context(
        request,
        metadata={
            "result_count": sum(item.total for item in results),
            "completed_queries": len(results),
        },
    )

    return BatchQueryResponse(results=list(results))
