from __future__ import annotations

import asyncio
import time

from bigrag.exceptions import ValidationError
from bigrag.logging import get_logger
from bigrag.services._retrieval_filters import build_filter
from bigrag.services.embedding import EmbeddingModel
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.retrieval.cache import (
    RetrievalOutcome,
    cached_query_result,
    embed_query_with_cache,
    invalidate_collection_query_cache,
    query_result_cache_key,
    store_query_result,
)
from bigrag.services.retrieval.fusion import (
    keyword_score,
    reciprocal_rank_fusion,
    tokenize_query,
)
from bigrag.services.retrieval.log import log_query
from bigrag.services.retrieval.rerank import close_cohere_clients, rerank_results
from bigrag.services.runtime_settings import get_values
from bigrag.services.vector_store import VectorStoreFeatureError, VectorStoreProvider, vector_store

logger = get_logger("bigrag.retrieval")

MAX_TOP_K = 200


def _safe_create_task(coro, *, name: str) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)

    def _on_done(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            logger.warning("background task failed", task=name, error=repr(exc))

    task.add_done_callback(_on_done)
    return task


__all__ = [
    "MAX_TOP_K",
    "RetrievalOutcome",
    "close_cohere_clients",
    "invalidate_collection_query_cache",
    "rerank_results",
    "retrieve",
    "retrieve_multi",
]


def _supports_text_search(provider: VectorStoreProvider | None) -> bool:
    return vector_store.supports_text_search_for(provider)


async def retrieve(
    collection_name: str,
    query: str,
    embedding_model: EmbeddingModel,
    top_k: int = 10,
    filters: dict | None = None,
    min_score: float | None = None,
    search_mode: str = "semantic",
    reranking_config: dict | None = None,
    rerank_override: bool | None = None,
    vector_store_provider: VectorStoreProvider | None = None,
) -> RetrievalOutcome:
    if top_k > MAX_TOP_K:
        raise ValidationError(f"top_k {top_k} exceeds maximum {MAX_TOP_K}")
    _retrieve_start = time.monotonic()
    timings = {"embed_ms": 0.0, "search_ms": 0.0, "rerank_ms": 0.0}

    event_bus.publish(
        IngestionEvent(
            document_id="",
            step="search",
            status="processing",
            message=f"Searching: {query[:80]}",
            detail={"top_k": top_k, "mode": search_mode},
            collection_name=collection_name,
        )
    )
    try:
        filter_expr = build_filter(filters) if filters else None
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    if search_mode in {"keyword", "hybrid"} and not _supports_text_search(vector_store_provider):
        provider_label = vector_store_provider or vector_store.provider
        raise ValidationError(f"{provider_label} does not support {search_mode} search in v1")
    query_terms = tokenize_query(query)

    query_embedding: list[float] | None = None
    result_cache_key: str | None = None
    cache_settings = await get_values(["query_result_cache_ttl"])
    if cache_settings["query_result_cache_ttl"] > 0:
        cache_t0 = time.monotonic()
        result_cache_key = await query_result_cache_key(
            collection_name=collection_name,
            query=query,
            embedding_model=embedding_model,
            top_k=top_k,
            filters=filters,
            min_score=min_score,
            search_mode=search_mode,
            reranking_config=reranking_config,
            rerank_override=rerank_override,
        )
        cached_outcome = await cached_query_result(result_cache_key)
        if cached_outcome is not None:
            cache_ms = (time.monotonic() - cache_t0) * 1000
            total_ms = (time.monotonic() - _retrieve_start) * 1000
            cached_outcome.cache_ms = round(cache_ms, 2)
            cached_outcome.total_ms = round(total_ms, 2)
            avg_score = (
                sum(r.get("score", 0) for r in cached_outcome.results) / len(cached_outcome.results)
                if cached_outcome.results
                else None
            )
            _safe_create_task(
                log_query(
                    collection_name=collection_name,
                    query=query,
                    top_k=top_k,
                    result_count=len(cached_outcome.results),
                    avg_score=avg_score,
                    latency_ms=cached_outcome.total_ms,
                    search_mode=search_mode,
                ),
                name="log_cached_query",
            )
            return cached_outcome

    if search_mode == "keyword":
        t0 = time.monotonic()
        try:
            raw_results = await vector_store.text_search(
                collection=collection_name,
                query_terms=query_terms,
                top_k=top_k,
                filters=filter_expr,
                provider=vector_store_provider,
            )
        except VectorStoreFeatureError as exc:
            raise ValidationError(str(exc)) from exc
        timings["search_ms"] = (time.monotonic() - t0) * 1000
        results = []
        for r in raw_results:
            score = keyword_score(r.get("text", ""), query_terms)
            if score > 0:
                r["score"] = round(score, 4)
                results.append(r)
        results.sort(key=lambda r: r["score"], reverse=True)
        results = results[:top_k]

    elif search_mode == "hybrid":
        t0 = time.monotonic()
        query_embedding = await embed_query_with_cache(query, embedding_model)
        timings["embed_ms"] = (time.monotonic() - t0) * 1000

        t0 = time.monotonic()
        fusion_pool = min(top_k * 5, MAX_TOP_K)
        semantic_task = vector_store.search(
            collection=collection_name,
            query_embedding=query_embedding,
            top_k=fusion_pool,
            filters=filter_expr,
            provider=vector_store_provider,
        )
        keyword_task = vector_store.text_search(
            collection=collection_name,
            query_terms=query_terms,
            top_k=fusion_pool,
            filters=filter_expr,
            provider=vector_store_provider,
        )
        try:
            semantic_results, keyword_raw = await asyncio.gather(semantic_task, keyword_task)
        except VectorStoreFeatureError as exc:
            raise ValidationError(str(exc)) from exc
        timings["search_ms"] = (time.monotonic() - t0) * 1000

        keyword_results = []
        for r in keyword_raw:
            score = keyword_score(r.get("text", ""), query_terms)
            if score > 0:
                r["score"] = round(score, 4)
                keyword_results.append(r)
        keyword_results.sort(key=lambda r: r["score"], reverse=True)

        results = reciprocal_rank_fusion([semantic_results, keyword_results])
        results = results[:top_k]

    else:
        t0 = time.monotonic()
        query_embedding = await embed_query_with_cache(query, embedding_model)
        timings["embed_ms"] = (time.monotonic() - t0) * 1000

        t0 = time.monotonic()
        results = await vector_store.search(
            collection=collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filter_expr,
            provider=vector_store_provider,
        )
        timings["search_ms"] = (time.monotonic() - t0) * 1000

    if reranking_config and results:
        should_rerank = reranking_config.get("enabled", False)
        if rerank_override is not None:
            should_rerank = rerank_override
        if should_rerank:
            t0 = time.monotonic()
            results = await rerank_results(
                results=results,
                query=query,
                model=reranking_config.get("model", "rerank-v3.5"),
                api_key=reranking_config.get("api_key"),
            )
            timings["rerank_ms"] = (time.monotonic() - t0) * 1000

    results = results[:top_k]

    if min_score is not None:
        results = [r for r in results if r.get("score", 0) >= min_score]

    total_ms = (time.monotonic() - _retrieve_start) * 1000
    timings["total_ms"] = total_ms
    avg_score = sum(r.get("score", 0) for r in results) / len(results) if results else None

    event_bus.publish(
        IngestionEvent(
            document_id="",
            step="search_complete",
            status="complete",
            message=f"{len(results)} results in {total_ms:.0f}ms",
            detail={
                "results": len(results),
                "latency_ms": round(total_ms, 1),
                "avg_score": round(avg_score, 4) if avg_score else 0,
                "mode": search_mode,
            },
            collection_name=collection_name,
        )
    )
    _safe_create_task(
        log_query(
            collection_name=collection_name,
            query=query,
            top_k=top_k,
            result_count=len(results),
            avg_score=avg_score,
            latency_ms=round(total_ms, 2),
            search_mode=search_mode,
        ),
        name="log_query",
    )

    outcome = RetrievalOutcome(
        results=results,
        embed_ms=round(timings["embed_ms"], 2),
        search_ms=round(timings["search_ms"], 2),
        rerank_ms=round(timings["rerank_ms"], 2),
        total_ms=round(total_ms, 2),
    )
    if result_cache_key is not None:
        await store_query_result(result_cache_key, outcome)
    return outcome


async def retrieve_multi(
    collection_names: list[str],
    query: str,
    embedding_models: dict[str, EmbeddingModel],
    top_k: int = 10,
    filters: dict | None = None,
    min_score: float | None = None,
    search_mode: str = "semantic",
    reranking_configs: dict[str, dict] | None = None,
    rerank_override: bool | None = None,
    vector_store_providers: dict[str, VectorStoreProvider] | None = None,
) -> list[dict]:
    if top_k > MAX_TOP_K:
        raise ValidationError(f"top_k {top_k} exceeds maximum {MAX_TOP_K}")

    async def search_one(col_name: str) -> list[dict]:
        col_reranking = (reranking_configs or {}).get(col_name)
        outcome = await retrieve(
            collection_name=col_name,
            query=query,
            embedding_model=embedding_models[col_name],
            top_k=top_k,
            filters=filters,
            min_score=min_score,
            search_mode=search_mode,
            reranking_config=col_reranking,
            rerank_override=rerank_override,
            vector_store_provider=(vector_store_providers or {}).get(col_name),
        )
        for r in outcome.results:
            r["collection"] = col_name
        return outcome.results

    all_results = await asyncio.wait_for(
        asyncio.gather(*[search_one(c) for c in collection_names]),
        timeout=120,
    )

    merged = []
    for results in all_results:
        merged.extend(results)

    merged.sort(key=lambda r: r.get("score", 0), reverse=True)
    return merged[:top_k]
