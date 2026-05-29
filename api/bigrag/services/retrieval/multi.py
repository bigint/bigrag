from __future__ import annotations

import asyncio

from bigrag.exceptions import ValidationError
from bigrag.services.embedding import EmbeddingModel
from bigrag.services.retrieval.constants import MAX_TOP_K, MULTI_SEARCH_CONCURRENCY
from bigrag.services.retrieval.orchestrate import retrieve


async def retrieve_multi(
    collection_names: list[str],
    query: str,
    embedding_models: dict[str, EmbeddingModel],
    top_k: int = 10,
    filters: dict | None = None,
    filters_by_collection: dict[str, dict | None] | None = None,
    min_score: float | None = None,
    search_mode: str = "semantic",
    reranking_configs: dict[str, dict] | None = None,
    rerank_override: bool | None = None,
    skip_cache: bool = False,
) -> list[dict]:
    if top_k > MAX_TOP_K:
        raise ValidationError(f"top_k {top_k} exceeds maximum {MAX_TOP_K}")

    semaphore = asyncio.Semaphore(MULTI_SEARCH_CONCURRENCY)

    async def search_one(col_name: str) -> list[dict]:
        async with semaphore:
            col_reranking = (reranking_configs or {}).get(col_name)
            col_filters = (
                filters_by_collection.get(col_name, filters)
                if filters_by_collection is not None
                else filters
            )
            outcome = await retrieve(
                collection_name=col_name,
                query=query,
                embedding_model=embedding_models[col_name],
                top_k=top_k,
                filters=col_filters,
                min_score=min_score,
                search_mode=search_mode,
                reranking_config=col_reranking,
                rerank_override=rerank_override,
                skip_cache=skip_cache,
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
