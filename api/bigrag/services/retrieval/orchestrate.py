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
    query_result_cache_key,
    store_query_result,
)
from bigrag.services.retrieval.fusion import tokenize_query
from bigrag.services.retrieval.log import (
    log_query,
    log_retrieval_cache_hit,
    log_retrieval_complete,
    log_retrieval_failed,
    log_retrieval_start,
)
from bigrag.services.retrieval.modes import hybrid_search, keyword_search, semantic_search
from bigrag.services.retrieval.rerank import rerank_results
from bigrag.services.runtime_settings import get_values

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
) -> RetrievalOutcome:
    if top_k > MAX_TOP_K:
        raise ValidationError(f"top_k {top_k} exceeds maximum {MAX_TOP_K}")
    _retrieve_start = time.monotonic()
    timings = {"embed_ms": 0.0, "search_ms": 0.0, "rerank_ms": 0.0}
    log_retrieval_start(
        collection_name=collection_name,
        top_k=top_k,
        search_mode=search_mode,
    )

    try:
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
        query_terms = tokenize_query(query)

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
                    sum(r.get("score", 0) for r in cached_outcome.results)
                    / len(cached_outcome.results)
                    if cached_outcome.results
                    else None
                )
                log_retrieval_cache_hit(
                    collection_name=collection_name,
                    result_count=len(cached_outcome.results),
                    total_ms=total_ms,
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
            results = await keyword_search(
                collection_name=collection_name,
                query_terms=query_terms,
                top_k=top_k,
                filter_expr=filter_expr,
                timings=timings,
            )
        elif search_mode == "hybrid":
            results, _ = await hybrid_search(
                collection_name=collection_name,
                query=query,
                query_terms=query_terms,
                embedding_model=embedding_model,
                top_k=top_k,
                max_top_k=MAX_TOP_K,
                filter_expr=filter_expr,
                timings=timings,
            )
        else:
            results, _ = await semantic_search(
                collection_name=collection_name,
                query=query,
                embedding_model=embedding_model,
                top_k=top_k,
                filter_expr=filter_expr,
                timings=timings,
            )

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
        log_retrieval_complete(
            collection_name=collection_name,
            result_count=len(results),
            timings=timings,
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
    except Exception as exc:
        log_retrieval_failed(
            collection_name=collection_name,
            elapsed_ms=(time.monotonic() - _retrieve_start) * 1000,
            exc=exc,
        )
        raise


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
