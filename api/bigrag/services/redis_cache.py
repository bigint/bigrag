"""Shared Redis cache with TTL support."""

from __future__ import annotations

import orjson
import redis.asyncio as aioredis

from bigrag.logging import get_logger

logger = get_logger("bigrag.redis_cache")

PREFIX = "bigrag:cache:"

_redis: aioredis.Redis | None = None


async def connect(redis_url: str) -> None:
    global _redis
    _redis = aioredis.from_url(redis_url, decode_responses=False)
    logger.info("redis cache connected")


async def close() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


async def get(key: str) -> dict | list | None:
    """Get a cached value by key. Returns None on miss."""
    if not _redis:
        return None
    raw = await _redis.get(f"{PREFIX}{key}")
    if raw is None:
        return None
    return orjson.loads(raw)


async def set(key: str, value: dict | list, ttl: int) -> None:
    """Set a cached value with TTL in seconds."""
    if not _redis:
        return
    await _redis.set(f"{PREFIX}{key}", orjson.dumps(value), ex=ttl)


async def delete(key: str) -> None:
    """Delete a cached value."""
    if not _redis:
        return
    await _redis.delete(f"{PREFIX}{key}")


async def delete_pattern(pattern: str) -> int:
    """Delete all keys matching a pattern. Returns count deleted."""
    if not _redis:
        return 0
    count = 0
    async for key in _redis.scan_iter(f"{PREFIX}{pattern}"):
        await _redis.delete(key)
        count += 1
    return count
