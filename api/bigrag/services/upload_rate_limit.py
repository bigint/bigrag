from __future__ import annotations

from bigrag.exceptions import RateLimitError
from bigrag.services.redis_cache import get_redis
from bigrag.services.runtime_settings import get_values

_WINDOW_SECONDS = 3600


def principal_upload_bucket(user: dict) -> str:
    key_id = user.get("api_key_id")
    if key_id:
        return f"api_key:{key_id}"
    return f"user:{user.get('id') or 'unknown'}"


async def consume_upload_budget(user: dict, *, files: int, bytes_: int) -> None:
    values = await get_values(["upload_rate_limit_files_per_hour", "upload_rate_limit_mb_per_hour"])
    file_limit = int(values["upload_rate_limit_files_per_hour"] or 0)
    byte_limit = int(values["upload_rate_limit_mb_per_hour"] or 0) * 1024 * 1024
    bucket = principal_upload_bucket(user)
    await _consume(
        f"upload:files:{bucket}",
        files,
        file_limit,
        "Too many uploaded files. Try again later.",
    )
    await _consume(
        f"upload:bytes:{bucket}",
        bytes_,
        byte_limit,
        "Upload byte quota exceeded. Try again later.",
    )


async def _consume(key: str, amount: int, limit: int, message: str) -> None:
    if amount <= 0 or limit <= 0:
        return
    redis = get_redis()
    if redis is None:
        return
    redis_key = f"bigrag:rate:{key}"
    total = await redis.incrby(redis_key, amount)
    if total == amount:
        await redis.expire(redis_key, _WINDOW_SECONDS)
    if total <= limit:
        return
    ttl = await redis.ttl(redis_key)
    retry_after = ttl if isinstance(ttl, int) and ttl > 0 else _WINDOW_SECONDS
    raise RateLimitError(message, retry_after=retry_after)
