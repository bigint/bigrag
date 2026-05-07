from __future__ import annotations

import hashlib

from bigrag.exceptions import RateLimitError
from bigrag.services.redis_cache import get_redis


def _key(bucket: str, identifier: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    return f"bigrag:rate:{bucket}:{digest}"


async def consume_rate_limit(
    *,
    bucket: str,
    identifier: str,
    limit: int,
    window_seconds: int,
    message: str,
) -> None:
    if limit <= 0 or window_seconds <= 0:
        return
    redis = get_redis()
    if redis is None:
        return

    key = _key(bucket, identifier)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    if count <= limit:
        return

    ttl = await redis.ttl(key)
    retry_after = ttl if isinstance(ttl, int) and ttl > 0 else window_seconds
    raise RateLimitError(message, retry_after=retry_after)
