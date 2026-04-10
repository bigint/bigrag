from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models.common import StatusResponse
from bigrag.models.query import (
    AnalyticsResponse,
    BatchQueryItem,
    BatchQueryRequest,
    BatchQueryResponse,
    BatchQueryResultItem,
    EmbeddingModelInfo,
    MultiQueryRequest,
    MultiQueryResponse,
    MultiQueryResult,
    QueryRequest,
    QueryResponse,
    QueryResult,
    VectorDeleteRequest,
    VectorUpsertRequest,
)
from bigrag.routers import get_collection_or_404, get_embedding_model_for, get_reranking_config
from bigrag.services.embedding import AVAILABLE_MODELS
from bigrag.services.retrieval import retrieve, retrieve_multi
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.routers.query")

router = APIRouter(tags=["query"])


@router.post("/v1/collections/{collection_name}/query", response_model=QueryResponse)
async def query_collection(
    collection_name: str,
    body: QueryRequest,
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)
    logger.info(
        f"query: collection={collection_name} q={body.query!r:.80s} "
        f"top_k={body.top_k} filters={body.filters}"
    )

    try:
        embedding_model = get_embedding_model_for(collection)
    except (ImportError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    top_k = body.top_k or collection.get("default_top_k", 10)
    min_score = (
        body.min_score if body.min_score is not None else collection.get("default_min_score")
    )
    search_mode = body.search_mode or collection.get("default_search_mode", "semantic")

    results = await retrieve(
        collection_name=collection_name,
        query=body.query,
        embedding_model=embedding_model,
        top_k=top_k,
        filters=body.filters,
        min_score=min_score,
        search_mode=search_mode,
        reranking_config=get_reranking_config(collection),
        rerank_override=body.rerank,
    )

    logger.info(f"query: collection={collection_name} results={len(results)}")
    return QueryResponse(
        results=[QueryResult(**r) for r in results],
        query=body.query,
        collection=collection_name,
        total=len(results),
    )


@router.post("/v1/query", response_model=MultiQueryResponse)
async def multi_collection_query(
    body: MultiQueryRequest,
    _: dict = Depends(get_current_user),
):
    logger.info(
        f"multi-query: collections={body.collections} q={body.query!r:.80s} top_k={body.top_k}"
    )

    embedding_models = {}
    reranking_configs = {}
    for col_name in body.collections:
        collection = await get_collection_or_404(col_name)
        try:
            embedding_models[col_name] = get_embedding_model_for(collection)
        except (ImportError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"Collection '{col_name}': {e}") from e
        reranking_configs[col_name] = get_reranking_config(collection)

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
    )

    logger.info(f"multi-query: collections={body.collections} results={len(results)}")
    return MultiQueryResponse(
        results=[MultiQueryResult(**r) for r in results],
        query=body.query,
        collections=body.collections,
        total=len(results),
    )


@router.post("/v1/batch/query", response_model=BatchQueryResponse)
async def batch_query(
    body: BatchQueryRequest,
    _: dict = Depends(get_current_user),
):
    logger.info(f"batch-query: {len(body.queries)} queries")

    async def run_one(item: BatchQueryItem) -> BatchQueryResultItem:
        collection = await get_collection_or_404(item.collection)
        try:
            embedding_model = get_embedding_model_for(collection)
        except (ImportError, ValueError) as e:
            msg = f"Collection '{item.collection}': {e}"
            raise HTTPException(status_code=400, detail=msg) from e

        results = await retrieve(
            collection_name=item.collection,
            query=item.query,
            embedding_model=embedding_model,
            top_k=item.top_k,
            filters=item.filters,
            min_score=item.min_score,
            search_mode=item.search_mode,
            reranking_config=get_reranking_config(collection),
            rerank_override=item.rerank,
        )

        return BatchQueryResultItem(
            results=[QueryResult(**r) for r in results],
            query=item.query,
            collection=item.collection,
            total=len(results),
        )

    results = await asyncio.gather(*[run_one(item) for item in body.queries])

    return BatchQueryResponse(results=list(results))


# Direct vector operations (for advanced users bringing their own embeddings)


@router.post("/v1/collections/{collection_name}/vectors/upsert", response_model=StatusResponse)
async def upsert_vectors(
    collection_name: str,
    body: VectorUpsertRequest,
    _: dict = Depends(get_current_user),
):
    await get_collection_or_404(collection_name)
    logger.info(f"upsert: collection={collection_name} vectors={len(body.vectors)}")

    ids = [v.id for v in body.vectors]
    embeddings = [v.embedding for v in body.vectors]
    texts = [v.text for v in body.vectors]
    metadata = [v.metadata for v in body.vectors]

    count = await vector_store.upsert(
        collection=collection_name,
        ids=ids,
        embeddings=embeddings,
        texts=texts,
        metadata=metadata,
    )
    logger.info(f"upsert: collection={collection_name} upserted={count}")

    return {"status": "ok", "upserted": count}


@router.post("/v1/collections/{collection_name}/vectors/delete", response_model=StatusResponse)
async def delete_vectors(
    collection_name: str,
    body: VectorDeleteRequest,
    _: dict = Depends(get_current_user),
):
    await get_collection_or_404(collection_name)
    logger.info(f"vectors/delete: collection={collection_name} ids={len(body.ids)}")
    await vector_store.delete_by_ids(collection_name, body.ids)
    return {"status": "ok", "deleted": len(body.ids)}


@router.get("/v1/collections/{collection_name}/analytics", response_model=AnalyticsResponse)
async def collection_analytics(
    collection_name: str,
    _: dict = Depends(get_current_user),
):
    await get_collection_or_404(collection_name)

    from bigrag.services import redis_cache

    cache_key = f"analytics:{collection_name}"
    cached = await redis_cache.get(cache_key)
    if cached:
        return AnalyticsResponse(**cached)

    from bigrag.database import db

    async def get_period_stats(interval: str) -> dict:
        row = await db.fetchrow(
            f"""
            SELECT
                COUNT(*) as query_count,
                COALESCE(AVG(latency_ms), 0) as avg_latency_ms,
                COALESCE(AVG(avg_score), 0) as avg_score,
                COALESCE(AVG(result_count), 0) as avg_result_count
            FROM query_log
            WHERE collection_name = $1 AND created_at > now() - interval '{interval}'
            """,
            collection_name,
        )
        return {
            "query_count": row["query_count"],
            "avg_latency_ms": round(float(row["avg_latency_ms"]), 2),
            "avg_score": round(float(row["avg_score"]), 4),
            "avg_result_count": round(float(row["avg_result_count"]), 1),
        }

    top_queries_rows = await db.fetch(
        """
        SELECT query, COUNT(*) as count
        FROM query_log
        WHERE collection_name = $1 AND created_at > now() - interval '7 days'
        GROUP BY query
        ORDER BY count DESC
        LIMIT 10
        """,
        collection_name,
    )

    stats_24h, stats_7d, stats_30d = await asyncio.gather(
        get_period_stats("24 hours"),
        get_period_stats("7 days"),
        get_period_stats("30 days"),
    )

    result = {
        "collection": collection_name,
        "period_24h": stats_24h,
        "period_7d": stats_7d,
        "period_30d": stats_30d,
        "top_queries": [{"query": r["query"], "count": r["count"]} for r in top_queries_rows],
    }
    await redis_cache.set(cache_key, result, ttl=300)

    return AnalyticsResponse(**result)


@router.get("/v1/embeddings/models")
async def list_embedding_models(_: dict = Depends(get_current_user)):
    return {"models": [EmbeddingModelInfo(**m).model_dump() for m in AVAILABLE_MODELS]}
