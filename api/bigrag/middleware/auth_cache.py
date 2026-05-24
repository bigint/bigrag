from __future__ import annotations

import asyncio

from bigrag.logging import get_logger
from bigrag.services import redis_cache

logger = get_logger("bigrag.auth")

REDIS_AUTH_TIMEOUT_SECONDS = 0.25


def session_cache_key(token_hash: str) -> str:
    return f"auth:session:{token_hash}"


def api_key_cache_key(key_hash: str) -> str:
    return f"auth:api_key:{key_hash}"


async def auth_cache_get(key: str) -> dict | list | None:
    try:
        return await asyncio.wait_for(redis_cache.get(key), timeout=REDIS_AUTH_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.debug("auth principal cache get unavailable", error=str(exc))
        return None


async def auth_cache_set(key: str, value: dict | list, ttl: int) -> None:
    try:
        await asyncio.wait_for(
            redis_cache.set(key, value, ttl=ttl),
            timeout=REDIS_AUTH_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.debug("auth principal cache set unavailable", error=str(exc))


async def auth_cache_delete(key: str) -> None:
    try:
        await asyncio.wait_for(redis_cache.delete(key), timeout=REDIS_AUTH_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.debug("auth principal cache delete unavailable", error=str(exc))


async def auth_cache_delete_pattern(pattern: str) -> None:
    await asyncio.wait_for(
        redis_cache.delete_pattern(pattern),
        timeout=REDIS_AUTH_TIMEOUT_SECONDS,
    )
