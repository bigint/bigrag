from __future__ import annotations

import asyncio
import hashlib
import random
import time
import uuid
from contextlib import asynccontextmanager

from bigrag.logging import get_logger
from bigrag.services import redis_cache
from bigrag.services.embedding_rate_limit import (
    RATE_LIMIT_COOLDOWN_KEY_PREFIX,
    is_rate_limit_error,
    rate_limit_delay,
    record_rate_limit_cooldown,
    wait_for_rate_limit_cooldown,
)

logger = get_logger("bigrag.embedding_gate")

MIN_LIMIT = 1.0
DECREASE_GUARD_MS = 1000
ACQUIRE_RETRY_MIN_MS = 25
ACQUIRE_RETRY_MAX_MS = 100
LEASE_SECONDS = 60
LIMIT_TTL_MS = 3_600_000

INFLIGHT_PREFIX = "bigrag:embedding:inflight:"
LIMIT_PREFIX = "bigrag:embedding:limit:"
LIMIT_DEC_PREFIX = "bigrag:embedding:limit-dec:"

_LOCAL_TOKEN = "__local__"
_FAILOPEN_TOKEN = "__failopen__"

_ACQUIRE_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
local limit = tonumber(redis.call('GET', KEYS[2]))
if limit == nil then limit = tonumber(ARGV[4]); redis.call('SET', KEYS[2], limit, 'PX', ARGV[6]) end
local count = redis.call('ZCARD', KEYS[1])
if count < math.floor(limit) then
  redis.call('ZADD', KEYS[1], ARGV[2], ARGV[3])
  redis.call('PEXPIRE', KEYS[1], ARGV[5])
  return 1
end
return 0
"""

_SUCCESS_LUA = """
local limit = tonumber(redis.call('GET', KEYS[1]))
if limit == nil then limit = tonumber(ARGV[1]) end
limit = limit + 1.0 / limit
if limit > tonumber(ARGV[1]) then limit = tonumber(ARGV[1]) end
redis.call('SET', KEYS[1], limit, 'PX', ARGV[2])
return tostring(limit)
"""

_DECREASE_LUA = """
local last = tonumber(redis.call('GET', KEYS[2])) or 0
local limit = tonumber(redis.call('GET', KEYS[1]))
if limit == nil then limit = tonumber(ARGV[2]) end
local changed = 0
if tonumber(ARGV[1]) - last > tonumber(ARGV[4]) then
  limit = limit * 0.5
  if limit < tonumber(ARGV[3]) then limit = tonumber(ARGV[3]) end
  redis.call('SET', KEYS[1], limit, 'PX', ARGV[5])
  redis.call('SET', KEYS[2], ARGV[1], 'PX', ARGV[5])
  changed = 1
end
return {tostring(limit), changed}
"""


class _LocalLimiter:
    def __init__(self, ceiling: float) -> None:
        self.limit = ceiling
        self.inflight = 0
        self.last_decrease = 0.0
        self.cond = asyncio.Condition()

    async def acquire(self) -> None:
        async with self.cond:
            while self.inflight >= int(self.limit):
                await self.cond.wait()
            self.inflight += 1

    async def release(self) -> None:
        async with self.cond:
            self.inflight = max(0, self.inflight - 1)
            self.cond.notify(1)

    async def on_success(self, ceiling: float) -> float:
        async with self.cond:
            self.limit = min(self.limit + 1.0 / self.limit, ceiling)
            self.cond.notify(1)
            return self.limit

    async def on_rate_limited(self) -> tuple[float, bool]:
        async with self.cond:
            now = time.monotonic()
            changed = False
            if now - self.last_decrease > DECREASE_GUARD_MS / 1000:
                self.limit = max(self.limit * 0.5, MIN_LIMIT)
                self.last_decrease = now
                changed = True
            return self.limit, changed


_local_limiters: dict[str, _LocalLimiter] = {}
_scripts: dict[str, tuple] = {}


def _ceiling() -> float:
    from bigrag.services.runtime_settings import sync_value

    return max(float(sync_value("embedding_concurrency")), MIN_LIMIT)


def _digest(cache_identity: str) -> str:
    return hashlib.sha256(str(cache_identity).encode()).hexdigest()[:24]


def _local(digest: str) -> _LocalLimiter:
    limiter = _local_limiters.get(digest)
    if limiter is None:
        limiter = _LocalLimiter(_ceiling())
        _local_limiters[digest] = limiter
    return limiter


def _script(redis, name: str, body: str):
    cached = _scripts.get(name)
    if cached is not None and cached[0] is redis:
        return cached[1]
    script = redis.register_script(body)
    _scripts[name] = (redis, script)
    return script


def _as_float(raw) -> float:
    if isinstance(raw, (bytes, bytearray)):
        return float(raw.decode())
    return float(raw)


def reset_embedding_limiters() -> None:
    _local_limiters.clear()


async def _acquire(redis, digest: str) -> str:
    if redis is None:
        await _local(digest).acquire()
        return _LOCAL_TOKEN
    inflight_key = INFLIGHT_PREFIX + digest
    limit_key = LIMIT_PREFIX + digest
    ceiling = _ceiling()
    script = _script(redis, "acquire", _ACQUIRE_LUA)
    while True:
        token = uuid.uuid4().hex
        now_ms = int(time.time() * 1000)
        try:
            ok = await script(
                keys=[inflight_key, limit_key],
                args=[
                    now_ms,
                    now_ms + LEASE_SECONDS * 1000,
                    token,
                    ceiling,
                    LEASE_SECONDS * 1000 * 2,
                    LIMIT_TTL_MS,
                ],
            )
        except Exception as exc:
            logger.debug("embedding gate acquire fell back", error=repr(exc))
            return _FAILOPEN_TOKEN
        if int(ok) == 1:
            return token
        await asyncio.sleep(random.uniform(ACQUIRE_RETRY_MIN_MS, ACQUIRE_RETRY_MAX_MS) / 1000)


async def _release(redis, digest: str, token: str) -> None:
    if token == _LOCAL_TOKEN:
        await _local(digest).release()
        return
    if token == _FAILOPEN_TOKEN or redis is None:
        return
    try:
        await redis.zrem(INFLIGHT_PREFIX + digest, token)
    except Exception as exc:
        logger.debug("embedding gate release failed", error=repr(exc))


async def _on_success(redis, digest: str) -> None:
    if redis is None:
        await _local(digest).on_success(_ceiling())
        return
    try:
        script = _script(redis, "success", _SUCCESS_LUA)
        await script(keys=[LIMIT_PREFIX + digest], args=[_ceiling(), LIMIT_TTL_MS])
    except Exception as exc:
        logger.debug("embedding gate success update failed", error=repr(exc))


async def _on_rate_limited(
    redis, digest: str, cooldown_key: str, exc: Exception, provider: str, model_name: str
) -> None:
    await record_rate_limit_cooldown(cooldown_key, rate_limit_delay(exc, 1.0))
    if redis is None:
        new_limit, changed = await _local(digest).on_rate_limited()
    else:
        try:
            script = _script(redis, "decrease", _DECREASE_LUA)
            now_ms = int(time.time() * 1000)
            raw = await script(
                keys=[LIMIT_PREFIX + digest, LIMIT_DEC_PREFIX + digest],
                args=[now_ms, _ceiling(), MIN_LIMIT, DECREASE_GUARD_MS, LIMIT_TTL_MS],
            )
            new_limit = _as_float(raw[0])
            changed = bool(int(raw[1]))
        except Exception as update_exc:
            logger.debug("embedding gate decrease failed", error=repr(update_exc))
            return
    if changed:
        logger.warning(
            "embedding limit decreased",
            provider=provider,
            model=model_name,
            new_limit=round(new_limit, 2),
        )


@asynccontextmanager
async def embedding_gate(cache_identity: str, provider: str, model_name: str):
    digest = _digest(cache_identity)
    cooldown_key = RATE_LIMIT_COOLDOWN_KEY_PREFIX + digest
    await wait_for_rate_limit_cooldown(cooldown_key, provider, model_name)
    redis = redis_cache.get_redis()
    token = await _acquire(redis, digest)
    err: Exception | None = None
    try:
        yield
    except BaseException as exc:
        err = exc
        raise
    finally:
        await _release(redis, digest, token)
        if err is None:
            await _on_success(redis, digest)
        elif is_rate_limit_error(err):
            await _on_rate_limited(redis, digest, cooldown_key, err, provider, model_name)
