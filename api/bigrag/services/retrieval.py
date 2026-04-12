from __future__ import annotations

import asyncio
import math
import re
import time
from dataclasses import dataclass, field

from bigrag.logging import get_logger
from bigrag.services.embedding import EmbeddingModel
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.vector_store import vector_store
from bigrag.utils import safe_create_task

logger = get_logger("bigrag.retrieval")


@dataclass
class RetrievalOutcome:
    """Return type of :func:`retrieve` — results plus per-phase timings and facets."""

    results: list[dict]
    embed_ms: float = 0.0
    search_ms: float = 0.0
    rerank_ms: float = 0.0
    hyde_ms: float = 0.0
    mmr_ms: float = 0.0
    total_ms: float = 0.0
    facets: dict[str, dict[str, int]] | None = None
    cached: bool = False
    # The embedded query vector — exposed so the semantic cache can
    # store/score entries without recomputing.
    query_embedding: list[float] | None = field(default=None, repr=False)


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


def _normalize_scores(items: list[dict]) -> list[dict]:
    """Min-max normalize scores into [0, 1]. Stable when all scores equal."""
    if not items:
        return items
    scores = [i.get("score", 0.0) for i in items]
    lo, hi = min(scores), max(scores)
    span = hi - lo
    out = []
    for item in items:
        copy = item.copy()
        if span <= 0:
            copy["score"] = 1.0 if item.get("score", 0.0) > 0 else 0.0
        else:
            copy["score"] = (item.get("score", 0.0) - lo) / span
        out.append(copy)
    return out


def _weighted_fusion(
    ranked_lists: list[list[dict]],
    weights: list[float] | None = None,
) -> list[dict]:
    """Merge lists by weighted sum of normalized scores. Falls back to
    equal weights."""
    weights = weights or [1.0] * len(ranked_lists)
    assert len(weights) == len(ranked_lists), "weights/lists length mismatch"

    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    for lst, w in zip(ranked_lists, weights, strict=False):
        normalized = _normalize_scores(lst)
        for item in normalized:
            item_id = item["id"]
            scores[item_id] = scores.get(item_id, 0.0) + w * item.get("score", 0.0)
            items.setdefault(item_id, item)

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    out = []
    for item_id in sorted_ids:
        entry = items[item_id].copy()
        entry["score"] = round(scores[item_id], 6)
        out.append(entry)
    return out


def fuse_results(
    ranked_lists: list[list[dict]],
    strategy: str = "rrf",
    weights: list[float] | None = None,
) -> list[dict]:
    """Dispatch to the configured hybrid fusion strategy."""
    if strategy == "weighted":
        return _weighted_fusion(ranked_lists, weights=weights)
    if strategy == "normalized":
        # Normalize first so a keyword score doesn't dominate cosine scores,
        # then RRF over the normalized order (rank is what counts in RRF).
        normalized = [_normalize_scores(lst) for lst in ranked_lists]
        return _reciprocal_rank_fusion(normalized)
    # Default: classic RRF over raw ranks.
    return _reciprocal_rank_fusion(ranked_lists)


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _cosine(a: list[float], b: list[float]) -> float:
    denom = _norm(a) * _norm(b)
    return _dot(a, b) / denom if denom else 0.0


def mmr_rerank(
    results: list[dict],
    query_embedding: list[float],
    lambda_: float,
    top_k: int,
) -> list[dict]:
    """Maximal Marginal Relevance re-rank.

    ``lambda_`` trades relevance vs. diversity:

    - ``1.0`` → pure relevance (identical to input order)
    - ``0.0`` → pure novelty (picks points maximally unlike each other)

    Items without an ``embedding`` field are skipped from diversity
    comparison (they get no penalty). Missing-embedding items keep
    their original score so we don't destroy the ranking.
    """
    if lambda_ >= 1.0 or top_k >= len(results):
        return results[:top_k]

    remaining = list(results)
    picked: list[dict] = []
    # Pre-normalize query embedding once.
    q_norm = _norm(query_embedding)
    if not q_norm:
        return results[:top_k]

    while remaining and len(picked) < top_k:
        best_idx = 0
        best_score = -float("inf")
        for idx, candidate in enumerate(remaining):
            emb = candidate.get("embedding")
            relevance = candidate.get("score", 0.0)
            if not picked or not emb:
                # No peers yet — pure relevance, or no embedding to compare.
                mmr = lambda_ * relevance - (1 - lambda_) * 0.0
            else:
                max_sim = max(
                    _cosine(emb, p.get("embedding") or [])
                    for p in picked
                    if p.get("embedding")
                ) if any(p.get("embedding") for p in picked) else 0.0
                mmr = lambda_ * relevance - (1 - lambda_) * max_sim
            if mmr > best_score:
                best_score = mmr
                best_idx = idx
        picked.append(remaining.pop(best_idx))
    return picked


def compute_facets(
    results: list[dict],
    fields: list[str],
) -> dict[str, dict[str, int]]:
    """Aggregate counts per metadata value for each requested field.

    Missing or null values are skipped. Non-scalar values are coerced
    to their ``str()`` so operators like {"tags": ["a", "b"]} count
    the list as a single bucket — the caller can ask for the flattened
    form with a pre-processing pass if they need it.
    """
    facets: dict[str, dict[str, int]] = {f: {} for f in fields}
    for result in results:
        metadata = result.get("metadata") or {}
        for field_name in fields:
            value = metadata.get(field_name)
            if value is None:
                continue
            key = str(value) if not isinstance(value, (str, int, float, bool)) else str(value)
            facets[field_name][key] = facets[field_name].get(key, 0) + 1
    return facets


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


async def _hyde_expand(
    query: str,
    api_key: str | None,
) -> tuple[str, float]:
    """Generate a hypothetical answer via OpenAI and return it alongside
    elapsed ms. Falls back to the original query on any failure —
    HyDE is a boost, not a hard dependency.
    """
    t0 = time.monotonic()
    try:
        import openai

        client = openai.AsyncOpenAI(api_key=api_key)
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Write a concise, factual hypothetical answer "
                            "(2-4 sentences) that someone looking for this "
                            "information might write. The answer does NOT "
                            "need to be correct; it's used to broaden "
                            "semantic retrieval."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                max_tokens=200,
                temperature=0.3,
            ),
            timeout=15,
        )
        text = (resp.choices[0].message.content or "").strip()
        elapsed = (time.monotonic() - t0) * 1000
        if text:
            return f"{query}\n\n{text}", elapsed
    except Exception as exc:
        logger.warning("hyde: expansion failed, falling back to raw query", error=str(exc))
    return query, (time.monotonic() - t0) * 1000


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
    diversity: float | None = None,
    hybrid_strategy: str = "rrf",
    hyde: bool = False,
    hyde_api_key: str | None = None,
    facets: list[str] | None = None,
) -> RetrievalOutcome:
    """Run a retrieval and return an outcome with timings + facets.

    Backward-compat: callers that treat the return as ``list[dict]``
    will break — use ``outcome.results``.
    """
    _retrieve_start = time.monotonic()
    timings = {"embed_ms": 0.0, "search_ms": 0.0, "rerank_ms": 0.0, "hyde_ms": 0.0, "mmr_ms": 0.0}

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

    # Over-fetch when we'll MMR trim later, so diversity has headroom.
    fetch_k = top_k * 3 if (diversity is not None and diversity < 1.0) else top_k

    embed_query = query
    if hyde:
        embed_query, timings["hyde_ms"] = await _hyde_expand(query, hyde_api_key)

    query_embedding: list[float] | None = None

    if search_mode == "keyword":
        t0 = time.monotonic()
        raw_results = await vector_store.text_search(
            collection=collection_name,
            query_terms=query_terms,
            top_k=fetch_k,
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
        results = results[:fetch_k]

    elif search_mode == "hybrid":
        t0 = time.monotonic()
        embeddings = await embedding_model.embed([embed_query], input_type="query")
        query_embedding = embeddings[0]
        timings["embed_ms"] = (time.monotonic() - t0) * 1000

        t0 = time.monotonic()
        semantic_task = vector_store.search(
            collection=collection_name,
            query_embedding=query_embedding,
            top_k=fetch_k,
            filters=filter_expr,
        )
        keyword_task = vector_store.text_search(
            collection=collection_name,
            query_terms=query_terms,
            top_k=fetch_k,
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

        results = fuse_results(
            [semantic_results, keyword_results],
            strategy=hybrid_strategy,
        )
        results = results[:fetch_k]

    else:
        t0 = time.monotonic()
        embeddings = await embedding_model.embed([embed_query], input_type="query")
        query_embedding = embeddings[0]
        timings["embed_ms"] = (time.monotonic() - t0) * 1000

        t0 = time.monotonic()
        results = await vector_store.search(
            collection=collection_name,
            query_embedding=query_embedding,
            top_k=fetch_k,
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

    # MMR diversity, over-fetched candidates → top_k by relevance+novelty.
    if diversity is not None and diversity < 1.0 and query_embedding is not None and results:
        t0 = time.monotonic()
        results = mmr_rerank(
            results,
            query_embedding=query_embedding,
            lambda_=1.0 - diversity,  # caller's 0=pure_novelty ↔ MMR lambda
            top_k=top_k,
        )
        timings["mmr_ms"] = (time.monotonic() - t0) * 1000
    else:
        results = results[:top_k]

    if min_score is not None:
        results = [r for r in results if r.get("score", 0) >= min_score]

    total_ms = (time.monotonic() - _retrieve_start) * 1000
    timings["total_ms"] = total_ms
    avg_score = sum(r.get("score", 0) for r in results) / len(results) if results else None

    facet_counts = compute_facets(results, facets) if facets else None

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

    return RetrievalOutcome(
        results=results,
        embed_ms=round(timings["embed_ms"], 2),
        search_ms=round(timings["search_ms"], 2),
        rerank_ms=round(timings["rerank_ms"], 2),
        hyde_ms=round(timings["hyde_ms"], 2),
        mmr_ms=round(timings["mmr_ms"], 2),
        total_ms=round(total_ms, 2),
        facets=facet_counts,
        query_embedding=query_embedding,
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
    """Query multiple collections in parallel and merge results by score."""

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
