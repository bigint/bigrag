from __future__ import annotations

import secrets

from bigrag.services.redis_cache import get_redis

EVENT_TOKEN_TTL_SECONDS = 300
_PREFIX = "bigrag:event_token:"


async def create_event_token(user: dict, collection_name: str) -> str:
    token = secrets.token_urlsafe(32)
    redis = get_redis()
    if redis is None:
        raise RuntimeError("Redis is required for event tokens")
    payload = f"{user['id']}|{collection_name}"
    await redis.set(
        f"{_PREFIX}{token}",
        payload.encode("utf-8"),
        ex=EVENT_TOKEN_TTL_SECONDS,
    )
    return token


async def validate_event_token(
    token: str | None, collection_name: str, user: dict | None = None
) -> bool:
    if not token:
        return False
    redis = get_redis()
    if redis is None:
        return False
    key = f"{_PREFIX}{token}"
    raw = await redis.getdel(key)
    if raw is None:
        return False
    decoded = raw.decode("utf-8")
    if "|" in decoded:
        token_user_id, _, token_collection = decoded.partition("|")
    else:
        token_user_id, token_collection = "", decoded
    if token_collection != collection_name:
        return False
    if user is not None and token_user_id and token_user_id != str(user.get("id", "")):
        return False
    return True
