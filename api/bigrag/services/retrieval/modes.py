from __future__ import annotations

import asyncio
import time

from bigrag.exceptions import ValidationError
from bigrag.services._retrieval_filters import FilterExpression
from bigrag.services.embedding import EmbeddingModel
from bigrag.services.retrieval.cache import embed_query_with_cache
from bigrag.services.retrieval.fusion import keyword_patterns, keyword_score, reciprocal_rank_fusion
from bigrag.services.vector_store import vector_store


async def keyword_search(
    *,
    collection_name: str,
    query_terms: list[str],
    top_k: int,
    filter_expr: FilterExpression | None,
    timings: dict[str, float],
) -> list[dict]:
    t0 = time.monotonic()
    try:
        raw_results = await vector_store.text_search(
            collection=collection_name,
            query_terms=query_terms,
            top_k=top_k,
            filters=filter_expr,
        )
    except RuntimeError as exc:
        raise ValidationError(str(exc)) from exc
    timings["search_ms"] = (time.monotonic() - t0) * 1000

    patterns = keyword_patterns(query_terms)
    results = []
    for r in raw_results:
        score = keyword_score(r.get("text", ""), patterns)
        if score > 0:
            r["score"] = round(score, 4)
            results.append(r)
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


async def hybrid_search(
    *,
    collection_name: str,
    query: str,
    query_terms: list[str],
    embedding_model: EmbeddingModel,
    top_k: int,
    max_top_k: int,
    filter_expr: FilterExpression | None,
    timings: dict[str, float],
) -> tuple[list[dict], list[float] | None]:
    t0 = time.monotonic()
    query_embedding = await embed_query_with_cache(query, embedding_model)
    timings["embed_ms"] = (time.monotonic() - t0) * 1000

    t0 = time.monotonic()
    fusion_pool = min(top_k * 5, max_top_k)
    semantic_task = vector_store.search(
        collection=collection_name,
        query_embedding=query_embedding,
        top_k=fusion_pool,
        filters=filter_expr,
    )
    keyword_task = vector_store.text_search(
        collection=collection_name,
        query_terms=query_terms,
        top_k=fusion_pool,
        filters=filter_expr,
    )
    try:
        semantic_results, keyword_raw = await asyncio.gather(semantic_task, keyword_task)
    except RuntimeError as exc:
        raise ValidationError(str(exc)) from exc
    timings["search_ms"] = (time.monotonic() - t0) * 1000

    patterns = keyword_patterns(query_terms)
    keyword_results = []
    for r in keyword_raw:
        score = keyword_score(r.get("text", ""), patterns)
        if score > 0:
            r["score"] = round(score, 4)
            keyword_results.append(r)
    keyword_results.sort(key=lambda r: r["score"], reverse=True)

    results = reciprocal_rank_fusion([semantic_results, keyword_results])
    return results[:top_k], query_embedding


async def semantic_search(
    *,
    collection_name: str,
    query: str,
    embedding_model: EmbeddingModel,
    top_k: int,
    filter_expr: FilterExpression | None,
    timings: dict[str, float],
) -> tuple[list[dict], list[float]]:
    t0 = time.monotonic()
    query_embedding = await embed_query_with_cache(query, embedding_model)
    timings["embed_ms"] = (time.monotonic() - t0) * 1000

    t0 = time.monotonic()
    results = await vector_store.search(
        collection=collection_name,
        query_embedding=query_embedding,
        top_k=top_k,
        filters=filter_expr,
    )
    timings["search_ms"] = (time.monotonic() - t0) * 1000
    return results, query_embedding
