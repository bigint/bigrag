from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass

from bigrag.exceptions import ValidationError
from bigrag.logging import get_logger
from bigrag.services._retrieval_filters import build_filter
from bigrag.services.embedding import EmbeddingModel
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.vector_store import vector_store
from bigrag.utils import safe_create_task

logger = get_logger("bigrag.retrieval")


@dataclass
class RetrievalOutcome:
    results: list[dict]
    embed_ms: float = 0.0
    search_ms: float = 0.0
    rerank_ms: float = 0.0
    total_ms: float = 0.0


def _tokenize_query(query: str) -> list[str]:

    return [w.lower() for w in re.split(r"\s+", query.strip()) if len(w) >= 2]


def _keyword_score(text: str, query_terms: list[str]) -> float:

    text_lower = text.lower()
    if not query_terms:
        return 0.0
    matches = sum(1 for term in query_terms if term in text_lower)
    return matches / len(query_terms)


def _reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    k: int = 60,
) -> list[dict]:

    scores: dict[str, float] = {}
    items: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list):
            item_id = item["id"]
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)
            if item_id not in items:
                items[item_id] = item

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    result = []
    for item_id in sorted_ids:
        item = items[item_id].copy()
        item["score"] = round(scores[item_id], 6)
        result.append(item)

    return result


def fuse_results(ranked_lists: list[list[dict]]) -> list[dict]:
    return _reciprocal_rank_fusion(ranked_lists)


async def rerank_results(
    results: list[dict],
    query: str,
    model: str = "rerank-v3.5",
    api_key: str | None = None,
) -> list[dict]:

    if not results:
        return results

    try:
        import cohere
    except ImportError:
        logger.warning("cohere package not installed, skipping reranking")
        return results

    client = cohere.AsyncClient(api_key=api_key)
    try:
        texts = [r.get("text", "") for r in results]
        response = await asyncio.wait_for(
            client.rerank(
                query=query,
                documents=texts,
                model=model,
                top_n=len(results),
            ),
            timeout=30,
        )

        reranked = []
        for item in response.results:
            result = results[item.index].copy()
            result["score"] = round(item.relevance_score, 6)
            reranked.append(result)
        return reranked
    except Exception as e:
        logger.error(f"Reranking failed: {e!r}, returning original results")
        return results
    finally:
        await client.close()


async def _log_query(
    collection_name: str,
    query: str,
    top_k: int,
    result_count: int,
    avg_score: float | None,
    latency_ms: float,
    search_mode: str,
    collection_id: str | None = None,
) -> None:
    try:
        import uuid as _uuid

        import sqlalchemy as _sa

        from bigrag.db.engine import session_factory
        from bigrag.db.models import Collection, QueryLog

        async with session_factory()() as session:
            cid = None
            if collection_id is not None:
                try:
                    cid = _uuid.UUID(collection_id)
                except (TypeError, ValueError):
                    cid = None
            if cid is None:
                cid = await session.scalar(
                    _sa.select(Collection.id).where(Collection.name == collection_name)
                )
            session.add(
                QueryLog(
                    collection_id=cid,
                    collection_name=collection_name,
                    query=query[:500],
                    top_k=top_k,
                    result_count=result_count,
                    avg_score=avg_score,
                    latency_ms=latency_ms,
                    search_mode=search_mode,
                )
            )
            await session.commit()
    except Exception as e:
        logger.warning(f"Failed to log query: {e!r}")


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
    query_terms = _tokenize_query(query)

    query_embedding: list[float] | None = None

    if search_mode == "keyword":
        t0 = time.monotonic()
        raw_results = await vector_store.text_search(
            collection=collection_name,
            query_terms=query_terms,
            top_k=top_k,
            filters=filter_expr,
        )
        timings["search_ms"] = (time.monotonic() - t0) * 1000
        results = []
        for r in raw_results:
            score = _keyword_score(r.get("text", ""), query_terms)
            if score > 0:
                r["score"] = round(score, 4)
                results.append(r)
        results.sort(key=lambda r: r["score"], reverse=True)
        results = results[:top_k]

    elif search_mode == "hybrid":
        t0 = time.monotonic()
        embeddings = await embedding_model.embed([query], input_type="query")
        query_embedding = embeddings[0]
        timings["embed_ms"] = (time.monotonic() - t0) * 1000

        t0 = time.monotonic()
        semantic_task = vector_store.search(
            collection=collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filter_expr,
        )
        keyword_task = vector_store.text_search(
            collection=collection_name,
            query_terms=query_terms,
            top_k=top_k,
            filters=filter_expr,
        )
        semantic_results, keyword_raw = await asyncio.gather(semantic_task, keyword_task)
        timings["search_ms"] = (time.monotonic() - t0) * 1000

        keyword_results = []
        for r in keyword_raw:
            score = _keyword_score(r.get("text", ""), query_terms)
            if score > 0:
                r["score"] = round(score, 4)
                keyword_results.append(r)
        keyword_results.sort(key=lambda r: r["score"], reverse=True)

        results = fuse_results([semantic_results, keyword_results])
        results = results[:top_k]

    else:
        t0 = time.monotonic()
        embeddings = await embedding_model.embed([query], input_type="query")
        query_embedding = embeddings[0]
        timings["embed_ms"] = (time.monotonic() - t0) * 1000

        t0 = time.monotonic()
        results = await vector_store.search(
            collection=collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filter_expr,
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
    safe_create_task(
        _log_query(
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

    return RetrievalOutcome(
        results=results,
        embed_ms=round(timings["embed_ms"], 2),
        search_ms=round(timings["search_ms"], 2),
        rerank_ms=round(timings["rerank_ms"], 2),
        total_ms=round(total_ms, 2),
    )


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
