from __future__ import annotations

import hashlib

from bigrag.logging import get_logger
from bigrag.middleware._principal import principal_id
from bigrag.services import redis_cache

logger = get_logger("bigrag.idempotency")

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_DEFAULT_TTL_SECONDS = 24 * 60 * 60


def _cache_key(principal: str, idem_key: str, method: str, path: str) -> str:
    h = hashlib.sha256(f"{principal}|{idem_key}|{method}|{path}".encode()).hexdigest()
    return f"idem:{h}"


def _find_header(headers: list[tuple[bytes, bytes]], name: bytes) -> bytes | None:
    for k, v in headers:
        if k.lower() == name:
            return v
    return None


class IdempotencyMiddleware:
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
        principal = principal_id(scope)
        cache_key = _cache_key(principal, idem_key, method, path)

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
                    "body": body.decode("latin-1"),
                },
                ttl=self.ttl_seconds,
            )


async def _send_cached(send, cached: dict) -> None:
    headers = [
        (k.encode("latin-1"), v.encode("latin-1"))
        for k, v in cached.get("headers", [])
        if k.lower() != "content-length"
    ]
    body = cached["body"].encode("latin-1")
    headers.append((b"idempotency-key-replayed", b"true"))
    headers.append((b"content-length", str(len(body)).encode("ascii")))

    await send({"type": "http.response.start", "status": cached["status"], "headers": headers})
    await send({"type": "http.response.body", "body": body})
