"""Per-API-key / per-IP rate limiting.

Implements a fixed-window counter in Redis. Each request bumps a
counter keyed by ``(principal, endpoint_bucket, window_epoch)`` and
rejects anything over the configured limit with 429 + RFC 6585
headers.

Defaults are deliberately lenient so bursts during normal ingestion
work don't trip customers; customers can raise limits per-key later
by setting ``api_keys.rate_limits`` JSON.
"""

from __future__ import annotations

import math
import time

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from bigrag.logging import get_logger
from bigrag.middleware._principal import principal_id
from bigrag.services import redis_cache

logger = get_logger("bigrag.rate_limit")


# (method, path-prefix, limit-per-minute). First prefix match wins.
_RULES: list[tuple[str, str, int]] = [
    ("POST", "/v1/collections/{name}/documents", 10),
    ("POST", "/v1/collections/{name}/query", 60),
    ("POST", "/v1/query", 60),
    # Catch-all: generous default so healthy apps don't trip.
    ("*", "/v1/", 120),
]

_EXCLUDED_PREFIXES = ("/health", "/metrics", "/docs", "/openapi")


def _match_rule(method: str, path: str) -> tuple[str, int] | None:
    for rule_method, prefix, limit in _RULES:
        if rule_method != "*" and rule_method != method:
            continue
        # ``{name}`` is a single-segment placeholder.
        if _path_matches(path, prefix):
            return (f"{rule_method}:{prefix}", limit)
    return None


def _path_matches(path: str, pattern: str) -> bool:
    if "{" not in pattern:
        return path.startswith(pattern)
    p_parts = pattern.rstrip("/").split("/")
    a_parts = path.rstrip("/").split("/")
    if len(a_parts) < len(p_parts):
        return False
    for pp, ap in zip(p_parts, a_parts, strict=False):
        if pp.startswith("{") and pp.endswith("}"):
            continue
        if pp != ap:
            return False
    return True


class RateLimitMiddleware:
    """ASGI middleware enforcing per-principal rate limits."""

    def __init__(self, app: ASGIApp, window_seconds: int = 60) -> None:
        self.app = app
        self.window_seconds = window_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if any(path.startswith(p) for p in _EXCLUDED_PREFIXES):
            await self.app(scope, receive, send)
            return

        rule = _match_rule(scope["method"], path)
        if not rule:
            await self.app(scope, receive, send)
            return

        bucket, limit = rule
        headers = Headers(scope=scope)
        principal = principal_id(scope, headers)

        now = time.time()
        window_start = int(now // self.window_seconds) * self.window_seconds
        reset_at = window_start + self.window_seconds
        cache_key = f"rl:{principal}:{bucket}:{window_start}"

        count = await _incr(cache_key, ttl=self.window_seconds * 2)
        remaining = max(0, limit - count)

        if count > limit:
            retry_after = max(1, int(math.ceil(reset_at - now)))
            logger.warning(
                "rate_limit: throttled",
                principal=principal,
                bucket=bucket,
                count=count,
                limit=limit,
            )
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded, retry later.",
                    "limit": limit,
                    "window_seconds": self.window_seconds,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                },
            )
            await response(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers_list = list(message.get("headers") or [])
                headers_list.extend(
                    [
                        (b"x-ratelimit-limit", str(limit).encode("ascii")),
                        (b"x-ratelimit-remaining", str(remaining).encode("ascii")),
                        (b"x-ratelimit-reset", str(reset_at).encode("ascii")),
                    ]
                )
                message["headers"] = headers_list
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def _incr(key: str, ttl: int) -> int:
    """Atomic INCR with EXPIRE via the shared redis client.

    Returns the resulting count. If Redis is unavailable, returns 0 so
    the request is allowed through — rate limiting is best-effort, not
    a hard-fail surface.
    """
    client = redis_cache._redis  # noqa: SLF001 — intentional reuse of shared client
    if client is None:
        return 0
    pipe = client.pipeline()
    pipe.incr(key)
    pipe.expire(key, ttl)
    results = await pipe.execute()
    return int(results[0])
