from __future__ import annotations

import secrets

from bigrag.services.redis_cache import get_redis

EVENT_TOKEN_TTL_SECONDS = 300
_PREFIX = "bigrag:event_token:"


async def create_event_token(user: dict, collection_name: str) -> str:
    _ = user
    token = secrets.token_urlsafe(32)
    redis = get_redis()
    if redis is None:
        raise RuntimeError("Redis is required for event tokens")
    await redis.set(
        f"{_PREFIX}{token}",
        collection_name.encode("utf-8"),
        ex=EVENT_TOKEN_TTL_SECONDS,
    )
    return token


async def validate_event_token(token: str | None, collection_name: str) -> bool:
    if not token:
        return False
    redis = get_redis()
    if redis is None:
        return False
    key = f"{_PREFIX}{token}"
    raw = await redis.get(key)
    if raw is None:
        return False
    if raw.decode("utf-8") != collection_name:
        return False
    await redis.expire(key, EVENT_TOKEN_TTL_SECONDS)
    return True
