from __future__ import annotations

import asyncio
import random
import re
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from bigrag.logging import get_logger
from bigrag.services import redis_cache

logger = get_logger("bigrag.embedding_rate_limit")

MAX_RATE_LIMIT_RETRIES = 60
MAX_RATE_LIMIT_DELAY_SECONDS = 60.0
RATE_LIMIT_COOLDOWN_PADDING_SECONDS = 0.1
RATE_LIMIT_COOLDOWN_JITTER_SECONDS = 0.25
RATE_LIMIT_COOLDOWN_KEY_PREFIX = "bigrag:embedding:rate-limit:"
RATE_LIMIT_DELAY_RE = re.compile(
    r"try again in ([0-9]+(?:\.[0-9]+)?)\s*(ms|milliseconds?|s|sec|secs|seconds?)",
    re.IGNORECASE,
)
_local_rate_limit_until: dict[str, float] = {}
_local_rate_limit_lock = asyncio.Lock()


def is_rate_limit_error(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 429 or exc.__class__.__name__ == "RateLimitError"


def header_value(headers: object, name: str) -> str | None:
    get = getattr(headers, "get", None)
    if callable(get):
        value = get(name)
        if value is not None:
            return str(value)
    if isinstance(headers, Mapping):
        lower_name = name.lower()
        for key, value in headers.items():
            if str(key).lower() == lower_name:
                return str(value)
    return None


def retry_after_header_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())


def retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or getattr(exc, "headers", None)
    retry_after_ms = header_value(headers, "retry-after-ms")
    if retry_after_ms is not None:
        try:
            return max(0.0, float(retry_after_ms) / 1000)
        except ValueError:
            pass
    retry_after = retry_after_header_seconds(header_value(headers, "retry-after"))
    if retry_after is not None:
        return retry_after
    for text in (str(exc), repr(exc)):
        match = RATE_LIMIT_DELAY_RE.search(text)
        if match is None:
            continue
        amount = float(match.group(1))
        unit = match.group(2).lower()
        return amount / 1000 if unit.startswith("m") else amount
    return None


def rate_limit_delay(exc: Exception, fallback: float) -> float:
    retry_after = retry_after_seconds(exc)
    delay = fallback if retry_after is None else retry_after
    return min(max(delay, 0.0), MAX_RATE_LIMIT_DELAY_SECONDS)


async def cooldown_delay(key: str) -> float:
    redis = redis_cache.get_redis()
    if redis is not None:
        ttl_ms = await redis.pttl(key)
        return ttl_ms / 1000 if ttl_ms and ttl_ms > 0 else 0.0
    async with _local_rate_limit_lock:
        return max(0.0, _local_rate_limit_until.get(key, 0.0) - time.monotonic())


async def wait_for_rate_limit_cooldown(key: str, provider: str, model_name: str) -> None:
    while True:
        delay = await cooldown_delay(key)
        if delay <= 0:
            return
        wait = min(
            delay + random.uniform(0, RATE_LIMIT_COOLDOWN_JITTER_SECONDS),
            MAX_RATE_LIMIT_DELAY_SECONDS,
        )
        logger.warning(
            "embedding rate limit cooldown active",
            provider=provider,
            model=model_name,
            retrying_in=round(wait, 3),
        )
        await asyncio.sleep(wait)


async def record_rate_limit_cooldown(key: str, delay: float) -> None:
    ttl = min(
        max(delay + RATE_LIMIT_COOLDOWN_PADDING_SECONDS, RATE_LIMIT_COOLDOWN_PADDING_SECONDS),
        MAX_RATE_LIMIT_DELAY_SECONDS,
    )
    redis = redis_cache.get_redis()
    if redis is not None:
        ttl_ms = max(1, int(ttl * 1000))
        lua = (
            "local cur = redis.call('PTTL', KEYS[1]) "
            "if cur == -2 or cur == -1 or tonumber(ARGV[1]) > cur then "
            "redis.call('SET', KEYS[1], '1', 'PX', ARGV[1]) return 1 end return 0"
        )
        await redis.eval(lua, 1, key, ttl_ms)
        return
    async with _local_rate_limit_lock:
        _local_rate_limit_until[key] = max(
            _local_rate_limit_until.get(key, 0.0),
            time.monotonic() + ttl,
        )
