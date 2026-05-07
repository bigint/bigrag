from __future__ import annotations

import orjson
import redis.asyncio as aioredis

from bigrag.logging import get_logger
from bigrag.services import crypto

logger = get_logger("bigrag.redis_cache")

PREFIX = "bigrag:cache:"
ENCRYPTED_PREFIX = b"bigrag-fernet:"

_redis: aioredis.Redis | None = None


async def connect(redis_url: str) -> None:
    global _redis
    _redis = aioredis.from_url(redis_url, decode_responses=False)
    logger.info("redis cache connected")


def get_redis() -> aioredis.Redis | None:
    return _redis


async def close() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


async def get(key: str) -> dict | list | None:

    if not _redis:
        return None
    raw = await _redis.get(f"{PREFIX}{key}")
    if raw is None:
        return None
    return _decode_value(raw)


async def set(key: str, value: dict | list, ttl: int) -> None:

    if not _redis:
        return
    await _redis.set(f"{PREFIX}{key}", _encode_value(value), ex=ttl)


async def delete(key: str) -> None:

    if not _redis:
        return
    await _redis.delete(f"{PREFIX}{key}")


async def delete_pattern(pattern: str) -> int:

    if not _redis:
        return 0
    count = 0
    async for key in _redis.scan_iter(f"{PREFIX}{pattern}"):
        await _redis.delete(key)
        count += 1
    return count


def _encode_value(value: dict | list) -> bytes:
    raw = orjson.dumps(value)
    if not crypto.is_configured():
        return raw
    return ENCRYPTED_PREFIX + crypto.encrypt_bytes(raw)


def _decode_value(raw: bytes) -> dict | list | None:
    payload = raw
    if raw.startswith(ENCRYPTED_PREFIX):
        try:
            payload = crypto.decrypt_bytes(raw[len(ENCRYPTED_PREFIX) :])
        except Exception as exc:
            logger.debug("redis cache decrypt failed", error=str(exc))
            return None
    try:
        return orjson.loads(payload)
    except Exception as exc:
        logger.debug("redis cache decode failed", error=str(exc))
        return None
