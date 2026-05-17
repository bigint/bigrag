from __future__ import annotations

import asyncio

import sqlalchemy as sa

from bigrag import __version__
from bigrag.db.engine import session_factory
from bigrag.logging import get_logger
from bigrag.services import redis_cache
from bigrag.services.runtime_settings import get_values

logger = get_logger("bigrag.services.health")

_EMBEDDING_HEALTH_TTL = 60
READINESS_TTL = 10
READINESS_CACHE_KEY = "health:readiness"


_AUTH_TOKENS = ("401", "unauthor", "invalid api key", "invalid_api_key")
_RATE_TOKENS = ("429", "rate", "quota")
_TIMEOUT_TOKENS = ("timeout", "timed out")
_NETWORK_TOKENS = ("connection", "network", "unreachable", "dns")
_MISCONFIGURED_TOKENS = (
    "not configured",
    "client not connected",
    "invalid url",
    "missing",
    "misconfigured",
)


def categorize_dependency_error(exc: Exception) -> str:
    text = f"{exc.__class__.__name__}: {exc}".lower()
    if any(t in text for t in _AUTH_TOKENS):
        return "auth_failed"
    if any(t in text for t in _RATE_TOKENS):
        return "rate_limited"
    if any(t in text for t in _TIMEOUT_TOKENS):
        return "timeout"
    if any(t in text for t in _NETWORK_TOKENS):
        return "unreachable"
    if any(t in text for t in _MISCONFIGURED_TOKENS):
        return "misconfigured"
    return "unknown"


async def cache_get(key: str) -> dict | list | None:
    try:
        return await redis_cache.get(key)
    except Exception as exc:
        logger.warning("health cache get failed", key=key, error=repr(exc))
        return None


async def cache_set(key: str, value: dict | list, ttl: int) -> None:
    try:
        await redis_cache.set(key, value, ttl=ttl)
    except Exception as exc:
        logger.warning("health cache set failed", key=key, error=repr(exc))


async def resolve_embedding_target() -> (
    tuple[str, str, int | None, str, str | None, str | None] | None
):
    runtime = await get_values(
        [
            "embedding_provider",
            "embedding_model",
            "embedding_dimension",
            "embedding_api_key",
            "embedding_base_url",
        ]
    )

    if runtime["embedding_api_key"]:
        return (
            runtime["embedding_provider"],
            runtime["embedding_model"],
            runtime["embedding_dimension"],
            runtime["embedding_api_key"],
            runtime["embedding_base_url"],
            "settings",
        )

    from bigrag.db.models import Collection, EmbeddingPreset

    async with session_factory()() as session:
        preset = await session.scalar(
            sa.select(EmbeddingPreset)
            .where(EmbeddingPreset.api_key.is_not(None))
            .where(EmbeddingPreset.api_key != "")
            .order_by(EmbeddingPreset.created_at.asc())
            .limit(1)
        )
        if preset is not None:
            return (
                preset.provider,
                preset.model,
                preset.dimension,
                preset.api_key,
                preset.base_url,
                "preset",
            )

        collection = await session.scalar(
            sa.select(Collection)
            .where(Collection.embedding_api_key.is_not(None))
            .where(Collection.embedding_api_key != "")
            .order_by(Collection.created_at.asc())
            .limit(1)
        )
        if collection is not None:
            return (
                collection.embedding_provider,
                collection.embedding_model,
                collection.dimension,
                collection.embedding_api_key,
                collection.embedding_base_url,
                "collection",
            )

    return None


async def check_embedding_provider() -> dict[str, object]:
    target = await resolve_embedding_target()
    if target is None:
        return {"embedding": False, "embedding_error": "no API key configured"}

    provider, model, dimension, api_key, base_url, source = target
    cache_key = f"health:embedding:{provider}:{source}"
    cached = await cache_get(cache_key)
    if cached:
        result: dict[str, object] = {"embedding": cached["ok"], "embedding_source": source}
        if cached.get("error"):
            result["embedding_error"] = cached["error"]
        return result

    try:
        from bigrag.services.embedding import get_embedding_model

        emb_model = get_embedding_model(
            provider=provider,
            model_name=model,
            dimension=dimension,
            api_key=api_key,
            base_url=base_url,
        )
        await asyncio.wait_for(emb_model.embed(["health check"], input_type="query"), timeout=10)
        await cache_set(cache_key, {"ok": True}, ttl=_EMBEDDING_HEALTH_TTL)
        return {"embedding": True, "embedding_source": source}
    except Exception as exc:
        category = categorize_dependency_error(exc)
        await cache_set(
            cache_key,
            {"ok": False, "error": category},
            ttl=_EMBEDDING_HEALTH_TTL,
        )
        logger.warning(
            "embedding health check failed",
            provider=provider,
            source=source,
            category=category,
            error=repr(exc),
        )
        return {
            "embedding": False,
            "embedding_error": category,
            "embedding_source": source,
        }


async def readiness_status(vs, queue) -> tuple[dict[str, object], bool]:
    cached = await cache_get(READINESS_CACHE_KEY)
    if cached:
        return cached, cached.get("status") == "ok"

    checks: dict[str, object] = {"version": __version__}
    healthy = True

    async def _check_postgres():
        async with session_factory()() as session:
            await session.execute(sa.text("SELECT 1"))

    async def _check_vector_store():
        if vs.client:
            await vs.health_check()
        else:
            raise RuntimeError("vector store client not connected")

    async def _check_redis():
        redis = getattr(queue, "redis", None) or getattr(queue, "_redis", None)
        await redis.ping()

    infra_checks = {
        "postgres": _check_postgres(),
        "vector_store": _check_vector_store(),
        "redis": _check_redis(),
    }

    results = await asyncio.gather(
        *infra_checks.values(),
        return_exceptions=True,
    )

    for name, result in zip(infra_checks.keys(), results, strict=False):
        if isinstance(result, Exception):
            checks[name] = False
            checks[f"{name}_error"] = categorize_dependency_error(result)
            healthy = False
        else:
            checks[name] = True
    checks["vector_store_provider"] = "per_collection"
    checks["qdrant"] = (
        checks["vector_store"] if "qdrant" in getattr(vs, "configured_providers", ()) else None
    )

    embedding_result = await check_embedding_provider()
    checks.update(embedding_result)
    if not embedding_result.get("embedding"):
        healthy = False

    checks["status"] = "ok" if healthy else "degraded"
    await cache_set(READINESS_CACHE_KEY, checks, ttl=READINESS_TTL)
    return checks, healthy
