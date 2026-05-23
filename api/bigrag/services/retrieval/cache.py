from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass

import orjson

from bigrag.logging import get_logger
from bigrag.services import redis_cache
from bigrag.services.access_log.payload import query_fingerprint
from bigrag.services.embedding import EmbeddingModel
from bigrag.services.runtime_settings import get_value

logger = get_logger("bigrag.retrieval")

QUERY_EPOCH_PREFIX = "bigrag:query_epoch:"
QUERY_CACHE_VERSION = 1
EMBEDDING_TIMEOUT_SECONDS = 60


@dataclass
class RetrievalOutcome:
    results: list[dict]
    embed_ms: float = 0.0
    search_ms: float = 0.0
    rerank_ms: float = 0.0
    cache_ms: float = 0.0
    total_ms: float = 0.0
    cache_hit: bool = False


def stable_hash(value: object) -> str:
    encoded = orjson.dumps(value, option=orjson.OPT_SORT_KEYS)
    return hashlib.sha256(encoded).hexdigest()


def embedding_identity(embedding_model: EmbeddingModel) -> str:
    explicit = getattr(embedding_model, "cache_identity", None)
    if isinstance(explicit, str) and explicit:
        return explicit
    return f"{embedding_model.provider}:{embedding_model.name}:{embedding_model.dimension}"


async def query_epoch(collection_name: str) -> int:
    redis = redis_cache.get_redis()
    if redis is None:
        return 0
    raw = await redis.get(f"{QUERY_EPOCH_PREFIX}{collection_name}")
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
    key = f"{QUERY_EPOCH_PREFIX}{collection_name}"
    await redis.incr(key)
    try:
        ttl = await get_value("query_result_cache_ttl")
    except Exception:
        ttl = 0
    expire_seconds = max(int(ttl) * 2, 3600) if ttl and int(ttl) > 0 else 172800
    await redis.expire(key, expire_seconds)


async def embed_query_with_cache(
    query: str,
    embedding_model: EmbeddingModel,
    *,
    skip_cache: bool = False,
) -> list[float]:
    ttl = await get_value("query_embedding_cache_ttl")
    if skip_cache or ttl <= 0:
        t0 = time.monotonic()
        logger.debug(
            "query_embedding_provider_request",
            provider=embedding_model.provider,
            model=embedding_model.name,
            dimension=embedding_model.dimension,
            cache_enabled=False,
            **query_fingerprint(query),
        )
        embeddings = await asyncio.wait_for(
            embedding_model.embed([query], input_type="query"),
            timeout=EMBEDDING_TIMEOUT_SECONDS,
        )
        logger.debug(
            "query_embedding_provider_response",
            provider=embedding_model.provider,
            model=embedding_model.name,
            dimension=embedding_model.dimension,
            vectors=len(embeddings),
            elapsed=round(time.monotonic() - t0, 2),
            **query_fingerprint(query),
        )
        return embeddings[0]

    identity = embedding_identity(embedding_model)
    cache_key = f"query_embedding:{identity}:{stable_hash(query)}"
    cached = await redis_cache.get(cache_key)
    if isinstance(cached, list) and len(cached) == embedding_model.dimension:
        logger.debug(
            "query_embedding_cache_hit",
            provider=embedding_model.provider,
            model=embedding_model.name,
            dimension=embedding_model.dimension,
            **query_fingerprint(query),
        )
        return [float(v) for v in cached]

    t0 = time.monotonic()
    logger.debug(
        "query_embedding_provider_request",
        provider=embedding_model.provider,
        model=embedding_model.name,
        dimension=embedding_model.dimension,
        cache_enabled=True,
        **query_fingerprint(query),
    )
    embeddings = await asyncio.wait_for(
        embedding_model.embed([query], input_type="query"),
        timeout=EMBEDDING_TIMEOUT_SECONDS,
    )
    logger.debug(
        "query_embedding_provider_response",
        provider=embedding_model.provider,
        model=embedding_model.name,
        dimension=embedding_model.dimension,
        vectors=len(embeddings),
        elapsed=round(time.monotonic() - t0, 2),
        **query_fingerprint(query),
    )
    vector = embeddings[0]
    await redis_cache.set(cache_key, vector, ttl=ttl)
    return vector


async def query_result_cache_key(
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
    epoch = await query_epoch(collection_name)
    payload = {
        "version": QUERY_CACHE_VERSION,
        "collection": collection_name,
        "epoch": epoch,
        "query": query,
        "embedding": embedding_identity(embedding_model),
        "top_k": top_k,
        "filters": filters or {},
        "min_score": min_score,
        "search_mode": search_mode,
        "rerank_override": rerank_override,
        "reranking_enabled": (reranking_config or {}).get("enabled", False),
        "reranking_model": (reranking_config or {}).get("model"),
    }
    return f"query_result:{collection_name}:{stable_hash(payload)}"


async def cached_query_result(cache_key: str) -> RetrievalOutcome | None:
    cached = await redis_cache.get(cache_key)
    if not isinstance(cached, dict):
        return None
    results = cached.get("results")
    if not isinstance(results, list):
        return None
    return RetrievalOutcome(results=results, cache_hit=True)


async def store_query_result(cache_key: str, outcome: RetrievalOutcome) -> None:
    ttl = await get_value("query_result_cache_ttl")
    if ttl <= 0:
        return
    await redis_cache.set(
        cache_key,
        {
            "results": outcome.results,
        },
        ttl=ttl,
    )
