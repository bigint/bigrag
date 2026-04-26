from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
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
    QueryTimings,
    VectorDeleteRequest,
    VectorUpsertRequest,
)
from bigrag.routers import get_collection_or_404, get_embedding_model_for, get_reranking_config
from bigrag.services import semantic_cache
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

    use_semcache = body.use_semantic_cache if body.use_semantic_cache is not None else True

    precomputed_embedding: list[float] | None = None
    if use_semcache and not body.hyde and search_mode in ("semantic", "hybrid"):
        embeddings = await embedding_model.embed([body.query], input_type="query")
        precomputed_embedding = embeddings[0]
        cached = await semantic_cache.lookup(collection_name, precomputed_embedding)
        if cached:
            cached_copy = {**cached, "cached": True}
            return QueryResponse(**cached_copy)

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
        diversity=body.diversity,
        hybrid_strategy=body.hybrid_strategy or "rrf",
        hyde=bool(body.hyde),
        hyde_api_key=collection.get("embedding_api_key"),
        facets=body.facets,
        precomputed_embedding=precomputed_embedding,
    )

    logger.info(
        f"query: collection={collection_name} results={len(outcome.results)} "
        f"total_ms={outcome.total_ms}"
    )
    response = QueryResponse(
        results=[QueryResult(**_result_to_dict(r)) for r in outcome.results],
        query=body.query,
        collection=collection_name,
        total=len(outcome.results),
        timings=QueryTimings(
            embed_ms=outcome.embed_ms,
            search_ms=outcome.search_ms,
            rerank_ms=outcome.rerank_ms,
            hyde_ms=outcome.hyde_ms,
            mmr_ms=outcome.mmr_ms,
            total_ms=outcome.total_ms,
        ),
        facets=outcome.facets,
        cached=outcome.cached,
    )

    if use_semcache and outcome.query_embedding is not None and outcome.results:
        await semantic_cache.store(
            collection_name,
            outcome.query_embedding,
            response.model_dump(),
        )

    return response


def _result_to_dict(row: dict) -> dict:

    cleaned = {k: v for k, v in row.items() if k != "embedding"}
    metadata = cleaned.get("metadata") or {}
    for field_name in ("page_no", "char_start", "char_end"):
        if field_name in metadata and field_name not in cleaned:
            cleaned[field_name] = metadata[field_name]
    return cleaned


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
        )

        return BatchQueryResultItem(
            results=[QueryResult(**_result_to_dict(r)) for r in outcome.results],
            query=item.query,
            collection=item.collection,
            total=len(outcome.results),
        )

    results = await asyncio.gather(*[run_one(item) for item in body.queries])

    return BatchQueryResponse(results=list(results))


@router.post("/v1/collections/{collection_name}/vectors/upsert")
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


@router.post("/v1/collections/{collection_name}/vectors/delete")
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

    import sqlalchemy as sa

    from bigrag.db.engine import session_factory
    from bigrag.db.models import QueryLog

    async def get_period_stats(session, days: int) -> dict:
        since = sa.func.now() - sa.text("make_interval(days => :d)").bindparams(d=days)
        row = (
            await session.execute(
                sa.select(
                    sa.func.count().label("query_count"),
                    sa.func.coalesce(sa.func.avg(QueryLog.latency_ms), 0).label("avg_latency_ms"),
                    sa.func.coalesce(sa.func.avg(QueryLog.avg_score), 0).label("avg_score"),
                    sa.func.coalesce(sa.func.avg(QueryLog.result_count), 0).label(
                        "avg_result_count"
                    ),
                )
                .where(QueryLog.collection_name == collection_name)
                .where(QueryLog.created_at > since)
            )
        ).one()
        return {
            "query_count": row.query_count,
            "avg_latency_ms": round(float(row.avg_latency_ms), 2),
            "avg_score": round(float(row.avg_score), 4),
            "avg_result_count": round(float(row.avg_result_count), 1),
        }

    async with session_factory()() as session:
        top_queries_rows = (
            await session.execute(
                sa.select(QueryLog.query, sa.func.count().label("count"))
                .where(QueryLog.collection_name == collection_name)
                .where(QueryLog.created_at > sa.func.now() - sa.text("make_interval(days => 7)"))
                .group_by(QueryLog.query)
                .order_by(sa.desc("count"))
                .limit(10)
            )
        ).all()

        stats_24h, stats_7d, stats_30d = await asyncio.gather(
            get_period_stats(session, 1),
            get_period_stats(session, 7),
            get_period_stats(session, 30),
        )

    result = {
        "collection": collection_name,
        "period_24h": stats_24h,
        "period_7d": stats_7d,
        "period_30d": stats_30d,
        "top_queries": [{"query": r.query, "count": r.count} for r in top_queries_rows],
    }
    await redis_cache.set(cache_key, result, ttl=300)

    return AnalyticsResponse(**result)


@router.get("/v1/embeddings/models")
async def list_embedding_models(_: dict = Depends(get_current_user)):
    return {"models": [EmbeddingModelInfo(**m).model_dump() for m in AVAILABLE_MODELS]}
