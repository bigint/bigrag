"""Idempotency-Key middleware.

Implements the Stripe-style ``Idempotency-Key`` header convention: a
mutating request (POST/PUT/PATCH/DELETE) tagged with this header is
processed once; any retry with the same key replays the original
response byte-for-byte. Only 2xx responses are cached — clients can
still retry 4xx/5xx requests with the same key to get a different
result after fixing the input.

Keys are scoped by ``(key, method, path)`` so collisions across
endpoints are impossible. A 24-hour TTL prevents old keys from
accumulating. The replay response carries an
``Idempotency-Key-Replayed: true`` header so clients can distinguish
cached responses.
"""

from __future__ import annotations

import hashlib

from bigrag.logging import get_logger
from bigrag.services import redis_cache

logger = get_logger("bigrag.idempotency")

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_DEFAULT_TTL_SECONDS = 24 * 60 * 60


def _cache_key(idem_key: str, method: str, path: str) -> str:
    # Scope the cached result to (key, verb, path) so the same key used
    # on two different endpoints doesn't collide.
    h = hashlib.sha256(f"{idem_key}|{method}|{path}".encode()).hexdigest()
    return f"idem:{h}"


def _find_header(headers: list[tuple[bytes, bytes]], name: bytes) -> bytes | None:
    for k, v in headers:
        if k.lower() == name:
            return v
    return None


class IdempotencyMiddleware:
    """ASGI middleware implementing Idempotency-Key for mutating verbs."""

    def __init__(self, app, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self.app = app
        self.ttl_seconds = ttl_seconds

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in _MUTATING_METHODS:
            await self.app(scope, receive, send)
            return

        idem_raw = _find_header(scope.get("headers") or [], b"idempotency-key")
        if not idem_raw:
            await self.app(scope, receive, send)
            return

        idem_key = idem_raw.decode("latin-1").strip()
        if not idem_key:
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope.get("path", "")
        cache_key = _cache_key(idem_key, method, path)

        cached = await redis_cache.get(cache_key)
        if cached:
            logger.info(
                "idempotency: replaying cached response",
                method=method,
                path=path,
            )
            await _send_cached(send, cached)
            return

        status_code = 0
        body_chunks: list[bytes] = []
        response_headers: list[list[str]] = []

        async def send_wrapper(message):
            nonlocal status_code, response_headers
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = [
                    [k.decode("latin-1"), v.decode("latin-1")]
                    for k, v in (message.get("headers") or [])
                ]
            elif message["type"] == "http.response.body":
                chunk = message.get("body") or b""
                if chunk:
                    body_chunks.append(chunk)
            await send(message)

        await self.app(scope, receive, send_wrapper)

        if 200 <= status_code < 300:
            body = b"".join(body_chunks)
            await redis_cache.set(
                cache_key,
                {
                    "status": status_code,
                    "headers": response_headers,
                    # Store as latin-1-encoded str so orjson can round-trip
                    # any byte payload (JSON responses are usually utf-8;
                    # latin-1 is 1:1 for raw bytes).
                    "body": body.decode("latin-1"),
                },
                ttl=self.ttl_seconds,
            )


async def _send_cached(send, cached: dict) -> None:
    headers = [
        (k.encode("latin-1"), v.encode("latin-1"))
        for k, v in cached.get("headers", [])
        # Avoid replaying content-length of the new framing below.
        if k.lower() != "content-length"
    ]
    body = cached["body"].encode("latin-1")
    headers.append((b"idempotency-key-replayed", b"true"))
    headers.append((b"content-length", str(len(body)).encode("ascii")))

    await send({"type": "http.response.start", "status": cached["status"], "headers": headers})
    await send({"type": "http.response.body", "body": body})
