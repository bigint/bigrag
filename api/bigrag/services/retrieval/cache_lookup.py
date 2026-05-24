from __future__ import annotations

import time

from bigrag.services.embedding import EmbeddingModel
from bigrag.services.retrieval.cache import (
    RetrievalOutcome,
    cached_query_result,
    query_result_cache_key,
)
from bigrag.services.retrieval.log import log_query, log_retrieval_cache_hit
from bigrag.services.runtime_settings import get_values


async def serve_from_cache(
    *,
    collection_name: str,
    query: str,
    embedding_model: EmbeddingModel,
    top_k: int,
    filters: dict | None,
    min_score: float | None,
    search_mode: str,
    reranking_config: dict | None,
    rerank_override: bool | None,
    skip_cache: bool,
    retrieve_start: float,
) -> tuple[str | None, RetrievalOutcome | None]:
    if skip_cache:
        return None, None
    cache_settings = await get_values(["query_result_cache_ttl"])
    if cache_settings["query_result_cache_ttl"] <= 0:
        return None, None
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
    if cached_outcome is None:
        return result_cache_key, None
    cache_ms = (time.monotonic() - cache_t0) * 1000
    total_ms = (time.monotonic() - retrieve_start) * 1000
    cached_outcome.cache_ms = round(cache_ms, 2)
    cached_outcome.total_ms = round(total_ms, 2)
    avg_score = (
        sum(r.get("score", 0) for r in cached_outcome.results) / len(cached_outcome.results)
        if cached_outcome.results
        else None
    )
    log_retrieval_cache_hit(
        collection_name=collection_name,
        result_count=len(cached_outcome.results),
        total_ms=total_ms,
    )
    log_query(
        collection_name=collection_name,
        query=query,
        top_k=top_k,
        result_count=len(cached_outcome.results),
        avg_score=avg_score,
        latency_ms=cached_outcome.total_ms,
        search_mode=search_mode,
    )
    return result_cache_key, cached_outcome
