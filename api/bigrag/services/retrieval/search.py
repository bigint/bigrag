from __future__ import annotations

import time

from bigrag.services.embedding import EmbeddingModel
from bigrag.services.retrieval.constants import MAX_TOP_K
from bigrag.services.retrieval.modes import hybrid_search, keyword_search, semantic_search
from bigrag.services.retrieval.rerank import rerank_results


async def run_search_mode(
    *,
    collection_name: str,
    query: str,
    query_terms: list[str],
    embedding_model: EmbeddingModel,
    top_k: int,
    filter_expr,
    timings: dict[str, float],
    search_mode: str,
    skip_cache: bool,
) -> list[dict]:
    if search_mode == "keyword":
        return await keyword_search(
            collection_name=collection_name,
            query_terms=query_terms,
            top_k=top_k,
            filter_expr=filter_expr,
            timings=timings,
        )
    if search_mode == "hybrid":
        return await hybrid_search(
            collection_name=collection_name,
            query=query,
            query_terms=query_terms,
            embedding_model=embedding_model,
            top_k=top_k,
            max_top_k=MAX_TOP_K,
            filter_expr=filter_expr,
            timings=timings,
            skip_cache=skip_cache,
        )
    return await semantic_search(
        collection_name=collection_name,
        query=query,
        embedding_model=embedding_model,
        top_k=top_k,
        filter_expr=filter_expr,
        timings=timings,
        skip_cache=skip_cache,
    )


async def apply_reranking(
    *,
    results: list[dict],
    query: str,
    reranking_config: dict | None,
    rerank_override: bool | None,
    timings: dict[str, float],
) -> list[dict]:
    if not reranking_config or not results:
        return results
    should_rerank = reranking_config.get("enabled", False)
    if rerank_override is not None:
        should_rerank = rerank_override
    if not should_rerank:
        return results
    t0 = time.monotonic()
    reranked = await rerank_results(
        results=results,
        query=query,
        model=reranking_config.get("model", "rerank-v3.5"),
        api_key=reranking_config.get("api_key"),
    )
    timings["rerank_ms"] = (time.monotonic() - t0) * 1000
    return reranked
