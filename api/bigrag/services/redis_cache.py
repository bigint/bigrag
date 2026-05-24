from __future__ import annotations

import orjson
import redis.asyncio as aioredis

from bigrag.logging import get_logger
from bigrag.services import crypto

logger = get_logger("bigrag.redis_cache")

PREFIX = "bigrag:cache:"
ENCRYPTED_PREFIX = b"bigrag-fernet:"
MAX_CONNECTIONS = 200

_redis: aioredis.Redis | None = None


async def connect(redis_url: str) -> None:
    global _redis
    _redis = aioredis.from_url(redis_url, decode_responses=False, max_connections=MAX_CONNECTIONS)
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


async def set_if_absent(key: str, value: dict | list, ttl: int) -> bool:
    if not _redis:
        return True
    result = await _redis.set(f"{PREFIX}{key}", _encode_value(value), ex=ttl, nx=True)
    return bool(result)


async def delete(key: str) -> None:

    if not _redis:
        return
    await _redis.delete(f"{PREFIX}{key}")


async def delete_pattern(pattern: str) -> int:

    if not _redis:
        return 0
    count = 0
    batch: list[bytes | str] = []
    async for key in _redis.scan_iter(f"{PREFIX}{pattern}", count=500):
        batch.append(key)
        if len(batch) >= 500:
            pipe = _redis.pipeline()
            for k in batch:
                pipe.delete(k)
            await pipe.execute()
            count += len(batch)
            batch = []
    if batch:
        pipe = _redis.pipeline()
        for k in batch:
            pipe.delete(k)
        await pipe.execute()
        count += len(batch)
    return count


def _encode_value(value: dict | list) -> bytes:
    raw = orjson.dumps(value)
    if not crypto.is_configured():
        return raw
    return ENCRYPTED_PREFIX + crypto.encrypt_bytes(raw)


def _decode_value(raw: bytes) -> dict | list | None:
    if crypto.is_configured():
        if not raw.startswith(ENCRYPTED_PREFIX):
            logger.warning("redis cache value missing encrypted prefix while crypto is configured")
            return None
        try:
            payload = crypto.decrypt_bytes(raw[len(ENCRYPTED_PREFIX) :])
        except Exception as exc:
            logger.debug("redis cache decrypt failed", error=str(exc))
            return None
    else:
        payload = raw
    try:
        return orjson.loads(payload)
    except Exception as exc:
        logger.debug("redis cache decode failed", error=str(exc))
        return None
