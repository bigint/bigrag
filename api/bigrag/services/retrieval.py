from __future__ import annotations

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass

import orjson

from bigrag.exceptions import ValidationError
from bigrag.logging import get_logger
from bigrag.services import redis_cache
from bigrag.services._retrieval_filters import build_filter
from bigrag.services.embedding import EmbeddingModel
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.runtime_settings import get_value, get_values
from bigrag.services.vector_store import VectorStoreFeatureError, VectorStoreProvider, vector_store
from bigrag.utils import safe_create_task

logger = get_logger("bigrag.retrieval")

_QUERY_EPOCH_PREFIX = "bigrag:query_epoch:"
_QUERY_CACHE_VERSION = 1
_EMBEDDING_TIMEOUT_SECONDS = 60


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


def _stable_hash(value: object) -> str:
    encoded = orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
    return hashlib.sha256(encoded).hexdigest()


def _embedding_identity(embedding_model: EmbeddingModel) -> str:
    explicit = getattr(embedding_model, "cache_identity", None)
    if isinstance(explicit, str) and explicit:
        return explicit
    return f"{embedding_model.provider}:{embedding_model.name}:{embedding_model.dimension}"


async def _query_epoch(collection_name: str) -> int:
    redis = redis_cache.get_redis()
    if redis is None:
        return 0
    raw = await redis.get(f"{_QUERY_EPOCH_PREFIX}{collection_name}")
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


async def invalidate_collection_query_cache(collection_name: str) -> None:
    redis = redis_cache.get_redis()
    if redis is None:
        return
    await redis.incr(f"{_QUERY_EPOCH_PREFIX}{collection_name}")


async def _embed_query_with_cache(
    query: str,
    embedding_model: EmbeddingModel,
) -> list[float]:
    ttl = await get_value("query_embedding_cache_ttl")
    if ttl <= 0:
        embeddings = await asyncio.wait_for(
            embedding_model.embed([query], input_type="query"),
            timeout=_EMBEDDING_TIMEOUT_SECONDS,
        )
        return embeddings[0]

    identity = _embedding_identity(embedding_model)
    cache_key = f"query_embedding:{identity}:{_stable_hash(query)}"
    cached = await redis_cache.get(cache_key)
    if isinstance(cached, list) and len(cached) == embedding_model.dimension:
        return [float(v) for v in cached]

    embeddings = await asyncio.wait_for(
        embedding_model.embed([query], input_type="query"),
        timeout=_EMBEDDING_TIMEOUT_SECONDS,
    )
    vector = embeddings[0]
    await redis_cache.set(cache_key, vector, ttl=ttl)
    return vector


async def _query_result_cache_key(
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
) -> str:
    epoch = await _query_epoch(collection_name)
    payload = {
        "version": _QUERY_CACHE_VERSION,
        "collection": collection_name,
        "epoch": epoch,
        "query": query,
        "embedding": _embedding_identity(embedding_model),
        "top_k": top_k,
        "filters": filters or {},
        "min_score": min_score,
        "search_mode": search_mode,
        "rerank_override": rerank_override,
        "reranking_enabled": (reranking_config or {}).get("enabled", False),
        "reranking_model": (reranking_config or {}).get("model"),
    }
    return f"query_result:{collection_name}:{_stable_hash(payload)}"


async def _cached_query_result(cache_key: str) -> RetrievalOutcome | None:
    cached = await redis_cache.get(cache_key)
    if not isinstance(cached, dict):
        return None
    results = cached.get("results")
    if not isinstance(results, list):
        return None
    return RetrievalOutcome(
        results=results,
        embed_ms=float(cached.get("embed_ms", 0.0)),
        search_ms=float(cached.get("search_ms", 0.0)),
        rerank_ms=float(cached.get("rerank_ms", 0.0)),
        total_ms=float(cached.get("total_ms", 0.0)),
    )


async def _store_query_result(cache_key: str, outcome: RetrievalOutcome) -> None:
    ttl = await get_value("query_result_cache_ttl")
    if ttl <= 0:
        return
    await redis_cache.set(
        cache_key,
        {
            "results": outcome.results,
            "embed_ms": outcome.embed_ms,
            "search_ms": outcome.search_ms,
            "rerank_ms": outcome.rerank_ms,
            "total_ms": outcome.total_ms,
        },
        ttl=ttl,
    )


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
    except Exception as exc:
        logger.error("reranking failed", error=repr(exc))
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
    except Exception as exc:
        logger.warning("failed to log query", error=repr(exc))


MAX_TOP_K = 200


def _supports_text_search(provider: VectorStoreProvider | None) -> bool:
    if hasattr(vector_store, "supports_text_search_for"):
        return vector_store.supports_text_search_for(provider)
    return vector_store.supports_text_search


def _vector_store_label(provider: VectorStoreProvider | None) -> str:
    return provider or getattr(vector_store, "provider", "vector store")


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
    vector_store_provider: VectorStoreProvider | None = None,
) -> RetrievalOutcome:

    if top_k > MAX_TOP_K:
        raise ValidationError(f"top_k {top_k} exceeds maximum {MAX_TOP_K}")
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
    if search_mode in {"keyword", "hybrid"} and not _supports_text_search(vector_store_provider):
        provider_label = _vector_store_label(vector_store_provider)
        raise ValidationError(f"{provider_label} does not support {search_mode} search in v1")
    query_terms = _tokenize_query(query)

    query_embedding: list[float] | None = None
    result_cache_key: str | None = None
    cache_settings = await get_values(["query_result_cache_ttl"])
    if cache_settings["query_result_cache_ttl"] > 0:
        result_cache_key = await _query_result_cache_key(
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
        cached_outcome = await _cached_query_result(result_cache_key)
        if cached_outcome is not None:
            avg_score = (
                sum(r.get("score", 0) for r in cached_outcome.results) / len(cached_outcome.results)
                if cached_outcome.results
                else None
            )
            safe_create_task(
                _log_query(
                    collection_name=collection_name,
                    query=query,
                    top_k=top_k,
                    result_count=len(cached_outcome.results),
                    avg_score=avg_score,
                    latency_ms=0.0,
                    search_mode=search_mode,
                ),
                name="log_cached_query",
            )
            return cached_outcome

    if search_mode == "keyword":
        t0 = time.monotonic()
        try:
            raw_results = await vector_store.text_search(
                collection=collection_name,
                query_terms=query_terms,
                top_k=top_k,
                filters=filter_expr,
                provider=vector_store_provider,
            )
        except VectorStoreFeatureError as exc:
            raise ValidationError(str(exc)) from exc
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
        query_embedding = await _embed_query_with_cache(query, embedding_model)
        timings["embed_ms"] = (time.monotonic() - t0) * 1000

        t0 = time.monotonic()
        semantic_task = vector_store.search(
            collection=collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filter_expr,
            provider=vector_store_provider,
        )
        keyword_task = vector_store.text_search(
            collection=collection_name,
            query_terms=query_terms,
            top_k=top_k,
            filters=filter_expr,
            provider=vector_store_provider,
        )
        try:
            semantic_results, keyword_raw = await asyncio.gather(semantic_task, keyword_task)
        except VectorStoreFeatureError as exc:
            raise ValidationError(str(exc)) from exc
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
        query_embedding = await _embed_query_with_cache(query, embedding_model)
        timings["embed_ms"] = (time.monotonic() - t0) * 1000

        t0 = time.monotonic()
        results = await vector_store.search(
            collection=collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filter_expr,
            provider=vector_store_provider,
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

    outcome = RetrievalOutcome(
        results=results,
        embed_ms=round(timings["embed_ms"], 2),
        search_ms=round(timings["search_ms"], 2),
        rerank_ms=round(timings["rerank_ms"], 2),
        total_ms=round(total_ms, 2),
    )
    if result_cache_key is not None:
        await _store_query_result(result_cache_key, outcome)
    return outcome


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
    vector_store_providers: dict[str, VectorStoreProvider] | None = None,
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
            vector_store_provider=(vector_store_providers or {}).get(col_name),
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
