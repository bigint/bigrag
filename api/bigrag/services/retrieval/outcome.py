from __future__ import annotations

import time

from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.retrieval.cache import RetrievalOutcome
from bigrag.services.retrieval.log import log_query, log_retrieval_complete


def finalize_outcome(
    *,
    results: list[dict],
    timings: dict[str, float],
    retrieve_start: float,
    collection_name: str,
    query: str,
    top_k: int,
    search_mode: str,
) -> RetrievalOutcome:
    total_ms = (time.monotonic() - retrieve_start) * 1000
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
    log_query(
        collection_name=collection_name,
        query=query,
        top_k=top_k,
        result_count=len(results),
        avg_score=avg_score,
        latency_ms=round(total_ms, 2),
        search_mode=search_mode,
    )

    return RetrievalOutcome(
        results=results,
        embed_ms=round(timings["embed_ms"], 2),
        search_ms=round(timings["search_ms"], 2),
        rerank_ms=round(timings["rerank_ms"], 2),
        total_ms=round(total_ms, 2),
    )
