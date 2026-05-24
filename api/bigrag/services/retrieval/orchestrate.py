from __future__ import annotations

import time

from bigrag.exceptions import ValidationError
from bigrag.logging import get_logger
from bigrag.services._retrieval_filters import build_filter
from bigrag.services.embedding import EmbeddingModel
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.retrieval.cache import RetrievalOutcome, store_query_result
from bigrag.services.retrieval.cache_lookup import serve_from_cache
from bigrag.services.retrieval.constants import MAX_TOP_K
from bigrag.services.retrieval.fusion import tokenize_query
from bigrag.services.retrieval.log import (
    log_retrieval_failed,
    log_retrieval_start,
)
from bigrag.services.retrieval.outcome import finalize_outcome
from bigrag.services.retrieval.search import apply_reranking, run_search_mode

logger = get_logger("bigrag.retrieval")


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
    skip_cache: bool = False,
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

        result_cache_key, cached_outcome = await serve_from_cache(
            collection_name=collection_name,
            query=query,
            embedding_model=embedding_model,
            top_k=top_k,
            filters=filters,
            min_score=min_score,
            search_mode=search_mode,
            reranking_config=reranking_config,
            rerank_override=rerank_override,
            skip_cache=skip_cache,
            retrieve_start=_retrieve_start,
        )
        if cached_outcome is not None:
            return cached_outcome

        results = await run_search_mode(
            collection_name=collection_name,
            query=query,
            query_terms=query_terms,
            embedding_model=embedding_model,
            top_k=top_k,
            filter_expr=filter_expr,
            timings=timings,
            search_mode=search_mode,
            skip_cache=skip_cache,
        )
        results = await apply_reranking(
            results=results,
            query=query,
            reranking_config=reranking_config,
            rerank_override=rerank_override,
            timings=timings,
        )

        results = results[:top_k]

        if min_score is not None:
            results = [r for r in results if r.get("score", 0) >= min_score]

        outcome = finalize_outcome(
            results=results,
            timings=timings,
            retrieve_start=_retrieve_start,
            collection_name=collection_name,
            query=query,
            top_k=top_k,
            search_mode=search_mode,
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
