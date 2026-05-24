from __future__ import annotations

import time

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from bigrag import config as config_module
from bigrag.logging import get_logger
from bigrag.middleware.principal import principal_id
from bigrag.services.redis_cache import get_redis

logger = get_logger("bigrag.ratelimit")

_EXEMPT_PREFIXES = ("/health", "/mcp")
_EXPENSIVE_PREFIXES = ("/v1/query", "/v1/batch")


def _has_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)


def _limit_for(path: str) -> tuple[int, str]:
    s = config_module.settings
    if path.endswith("/query") or _has_prefix(path, _EXPENSIVE_PREFIXES):
        return s.rate_limit_query_per_minute, "q"
    return s.rate_limit_per_minute, "g"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        s = config_module.settings
        path = request.url.path
        if (
            not s.rate_limit_enabled
            or request.method.upper() == "OPTIONS"
            or _has_prefix(path, _EXEMPT_PREFIXES)
        ):
            return await call_next(request)

        redis = get_redis()
        if redis is None:
            return await call_next(request)

        window_seconds = s.rate_limit_window_seconds
        limit, tier = _limit_for(path)
        now = int(time.time())
        window_start = now - (now % window_seconds)
        principal = principal_id(request.scope, request.headers)
        bucket = f"bigrag:rate:{tier}:{window_start}:{principal}"
        try:
            pipeline = redis.pipeline()
            pipeline.incr(bucket)
            pipeline.expire(bucket, window_seconds)
            current = (await pipeline.execute())[0]
        except Exception as exc:
            logger.warning("rate limit unavailable; failing open", error=str(exc))
            return await call_next(request)

        if current > limit:
            retry_after = max(1, window_seconds - (now % window_seconds))
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Retry shortly."},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
