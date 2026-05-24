from __future__ import annotations

import os
import time

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from bigrag.logging import get_logger
from bigrag.middleware.principal import principal_id
from bigrag.services.redis_cache import get_redis

logger = get_logger("bigrag.ratelimit")

RATE_LIMIT_ENABLED = os.environ.get("BIGRAG_RATE_LIMIT_ENABLED", "1") not in {"0", "false", "False"}
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("BIGRAG_RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_PER_WINDOW = int(os.environ.get("BIGRAG_RATE_LIMIT_PER_MINUTE", "600"))
RATE_LIMIT_QUERY_PER_WINDOW = int(os.environ.get("BIGRAG_RATE_LIMIT_QUERY_PER_MINUTE", "120"))

_EXEMPT_PREFIXES = ("/health", "/mcp")
_EXPENSIVE_PREFIXES = ("/v1/query", "/v1/batch")


def _has_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)


def _limit_for(path: str) -> tuple[int, str]:
    if path.endswith("/query") or _has_prefix(path, _EXPENSIVE_PREFIXES):
        return RATE_LIMIT_QUERY_PER_WINDOW, "q"
    return RATE_LIMIT_PER_WINDOW, "g"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            not RATE_LIMIT_ENABLED
            or request.method.upper() == "OPTIONS"
            or _has_prefix(path, _EXEMPT_PREFIXES)
        ):
            return await call_next(request)

        redis = get_redis()
        if redis is None:
            return await call_next(request)

        limit, tier = _limit_for(path)
        now = int(time.time())
        window_start = now - (now % RATE_LIMIT_WINDOW_SECONDS)
        principal = principal_id(request.scope, request.headers)
        bucket = f"bigrag:rate:{tier}:{window_start}:{principal}"
        try:
            pipeline = redis.pipeline()
            pipeline.incr(bucket)
            pipeline.expire(bucket, RATE_LIMIT_WINDOW_SECONDS)
            current = (await pipeline.execute())[0]
        except Exception as exc:
            logger.warning("rate limit unavailable; failing open", error=str(exc))
            return await call_next(request)

        if current > limit:
            retry_after = max(1, RATE_LIMIT_WINDOW_SECONDS - (now % RATE_LIMIT_WINDOW_SECONDS))
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Retry shortly."},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
