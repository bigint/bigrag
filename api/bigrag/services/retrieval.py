from __future__ import annotations

import asyncio
import re
import time

from bigrag.logging import get_logger
from bigrag.services.embedding import EmbeddingModel
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.vector_store import vector_store
from bigrag.utils import safe_create_task

logger = get_logger("bigrag.retrieval")


def _tokenize_query(query: str) -> list[str]:
    """Split query into lowercase search terms, filtering short words."""
    return [w.lower() for w in re.split(r"\s+", query.strip()) if len(w) >= 2]


def _keyword_score(text: str, query_terms: list[str]) -> float:
    """Simple keyword relevance score based on term frequency."""
    text_lower = text.lower()
    if not query_terms:
        return 0.0
    matches = sum(1 for term in query_terms if term in text_lower)
    return matches / len(query_terms)


def _reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    k: int = 60,
) -> list[dict]:
    """Merge multiple ranked result lists using Reciprocal Rank Fusion (RRF).

    RRF score = sum(1 / (k + rank)) for each list where the item appears.
    """
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


async def rerank_results(
    results: list[dict],
    query: str,
    model: str = "rerank-v3.5",
    api_key: str | None = None,
) -> list[dict]:
    """Rerank results using Cohere Rerank API."""
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
) -> None:
    """Log a query for analytics. Fire-and-forget, errors are swallowed."""
    try:
        from bigrag.database import db

        await db.execute(
            """
            INSERT INTO query_log
                (collection_name, query, top_k, result_count, avg_score, latency_ms, search_mode)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            collection_name,
            query[:500],
            top_k,
            result_count,
            avg_score,
            latency_ms,
            search_mode,
        )
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
) -> list[dict]:
    """Embed query and search Milvus for similar chunks.

    search_mode: "semantic" (vector only), "keyword" (text match), "hybrid" (both + RRF).
    """
    _retrieve_start = time.monotonic()
    event_bus.publish(IngestionEvent(
        document_id="",
        step="search",
        status="processing",
        message=f"Searching: {query[:80]}",
        detail={"top_k": top_k, "mode": search_mode},
        collection_name=collection_name,
    ))
    filter_expr = _build_filter_expr(filters) if filters else None
    query_terms = _tokenize_query(query)

    if search_mode == "keyword":
        raw_results = await vector_store.text_search(
            collection=collection_name,
            query_terms=query_terms,
            top_k=top_k,
            filters=filter_expr,
        )
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
        embed_ms = (time.monotonic() - t0) * 1000
        logger.info(f"retrieve: embedded query collection={collection_name} {embed_ms:.0f}ms")

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

        keyword_results = []
        for r in keyword_raw:
            score = _keyword_score(r.get("text", ""), query_terms)
            if score > 0:
                r["score"] = round(score, 4)
                keyword_results.append(r)
        keyword_results.sort(key=lambda r: r["score"], reverse=True)

        results = _reciprocal_rank_fusion([semantic_results, keyword_results])
        results = results[:top_k]

    else:
        t0 = time.monotonic()
        embeddings = await embedding_model.embed([query], input_type="query")
        query_embedding = embeddings[0]
        embed_ms = (time.monotonic() - t0) * 1000
        logger.info(
            f"retrieve: embedded query collection={collection_name} "
            f"model={embedding_model.name} {embed_ms:.0f}ms"
        )

        t0 = time.monotonic()
        results = await vector_store.search(
            collection=collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filter_expr,
        )
        search_ms = (time.monotonic() - t0) * 1000
        logger.info(
            f"retrieve: searched collection={collection_name} "
            f"hits={len(results)} top_k={top_k} {search_ms:.0f}ms"
        )

    if reranking_config and results:
        should_rerank = reranking_config.get("enabled", False)
        if rerank_override is not None:
            should_rerank = rerank_override
        if should_rerank:
            results = await rerank_results(
                results=results,
                query=query,
                model=reranking_config.get("model", "rerank-v3.5"),
                api_key=reranking_config.get("api_key"),
            )

    if min_score is not None:
        results = [r for r in results if r.get("score", 0) >= min_score]

    total_ms = (time.monotonic() - _retrieve_start) * 1000
    avg_score = sum(r.get("score", 0) for r in results) / len(results) if results else None
    event_bus.publish(IngestionEvent(
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
    ))
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

    return results


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
    """Query multiple collections in parallel and merge results by score."""

    async def search_one(col_name: str) -> list[dict]:
        col_reranking = (reranking_configs or {}).get(col_name)
        results = await retrieve(
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
        for r in results:
            r["collection"] = col_name
        return results

    all_results = await asyncio.wait_for(
        asyncio.gather(*[search_one(c) for c in collection_names]),
        timeout=120,
    )

    merged = []
    for results in all_results:
        merged.extend(results)

    merged.sort(key=lambda r: r.get("score", 0), reverse=True)
    return merged[:top_k]


_SAFE_FIELD_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_field(key: str) -> str:
    """Validate that a field name is safe for use in filter expressions."""
    if not _SAFE_FIELD_RE.match(key):
        raise ValueError(f"Invalid filter field name: {key!r}")
    return key


def _escape_string(value: str) -> str:
    """Escape a string value for safe use in Milvus filter expressions."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _validate_scalar(val: object, op: str) -> None:
    """Ensure a filter value is a safe scalar (str, int, float, or bool)."""
    if not isinstance(val, (str, int, float, bool)):
        raise ValueError(f"Filter operator {op} requires a scalar value, got {type(val).__name__}")


def _format_value(val: str | int | float | bool) -> str:
    """Format a validated scalar for use in a Milvus filter expression."""
    if isinstance(val, str):
        return f'"{_escape_string(val)}"'
    if isinstance(val, bool):
        return "true" if val else "false"
    return str(val)


def _build_filter_expr(filters: dict) -> str | None:
    """Convert filter dict to Milvus filter expression."""
    expressions = []

    for key, value in filters.items():
        field = _validate_field(key)
        if isinstance(value, (str, int, float, bool)):
            expressions.append(f"{field} == {_format_value(value)}")
        elif isinstance(value, dict):
            for op, val in value.items():
                if op in ("$eq", "$ne"):
                    _validate_scalar(val, op)
                    sym = "==" if op == "$eq" else "!="
                    expressions.append(f"{field} {sym} {_format_value(val)}")
                elif op in ("$gt", "$gte", "$lt", "$lte"):
                    if not isinstance(val, (int, float)):
                        raise ValueError(
                            f"Filter operator {op} requires a numeric value, "
                            f"got {type(val).__name__}"
                        )
                    op_map = {"$gt": ">", "$gte": ">=", "$lt": "<", "$lte": "<="}
                    expressions.append(f"{field} {op_map[op]} {val}")
                elif op == "$in":
                    if not isinstance(val, list):
                        raise ValueError("Filter operator $in requires a list value")
                    safe_vals = []
                    for v in val:
                        _validate_scalar(v, "$in")
                        safe_vals.append(_format_value(v))
                    expressions.append(f"{field} in [{', '.join(safe_vals)}]")

    return " and ".join(expressions) if expressions else None
