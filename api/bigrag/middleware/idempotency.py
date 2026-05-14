from __future__ import annotations

import hashlib

import orjson

from bigrag.logging import get_logger
from bigrag.middleware._principal import principal_id
from bigrag.services import redis_cache

logger = get_logger("bigrag.idempotency")

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_DEFAULT_TTL_SECONDS = 24 * 60 * 60
_MAX_CACHED_BODY_BYTES = 64 * 1024
_MAX_REQUEST_BODY_BYTES = 8 * 1024 * 1024
_SENSITIVE_RESPONSE_HEADERS = frozenset({"content-length", "set-cookie"})


def _cache_key(principal: str, idem_key: str, method: str, path: str) -> str:
    h = hashlib.sha256(f"{principal}|{idem_key}|{method}|{path}".encode()).hexdigest()
    return f"idem:{h}"


def _find_header(headers: list[tuple[bytes, bytes]], name: bytes) -> bytes | None:
    for k, v in headers:
        if k.lower() == name:
            return v
    return None


async def _read_request_body(receive) -> tuple[bytes, bool, list[dict]]:
    chunks: list[bytes] = []
    messages: list[dict] = []
    total_size = 0
    while True:
        message = await receive()
        messages.append(message)
        if message["type"] != "http.request":
            break
        chunk = message.get("body") or b""
        if chunk:
            total_size += len(chunk)
            if total_size > _MAX_REQUEST_BODY_BYTES:
                return b"", False, messages
            chunks.append(chunk)
        if not message.get("more_body", False):
            break
    return b"".join(chunks), True, messages


def _request_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _replay_receive(messages: list[dict]):
    remaining = list(messages)

    async def receive():
        if remaining:
            return remaining.pop(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    return receive


async def _send_conflict(send) -> None:
    body = orjson.dumps(
        {"detail": "Idempotency-Key was already used with a different request body"}
    )
    await send(
        {
            "type": "http.response.start",
            "status": 409,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class IdempotencyMiddleware:
    def __init__(self, app, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self.app = app
        self.ttl_seconds = ttl_seconds

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in _MUTATING_METHODS:
            await self.app(scope, receive, send)
            return
        if str(scope.get("path", "")).startswith("/v1/auth"):
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
        request_body, can_fingerprint, messages = await _read_request_body(receive)
        if not can_fingerprint:
            await self.app(scope, _replay_receive(messages), send)
            return
        fingerprint = _request_hash(request_body)

        cached = await redis_cache.get(cache_key)
        if cached:
            if cached.get("request_hash") != fingerprint:
                await _send_conflict(send)
                return
            logger.info(
                "idempotency: replaying cached response",
                method=method,
                path=path,
            )
            await _send_cached(send, cached)
            return

        status_code = 0
        body_chunks: list[bytes] = []
        body_size = 0
        cacheable_body = True
        response_headers: list[list[str]] = []

        async def send_wrapper(message):
            nonlocal body_size, cacheable_body, response_headers, status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = [
                    [k.decode("latin-1"), v.decode("latin-1")]
                    for k, v in (message.get("headers") or [])
                ]
            elif message["type"] == "http.response.body":
                chunk = message.get("body") or b""
                if chunk:
                    body_size += len(chunk)
                    if cacheable_body and body_size <= _MAX_CACHED_BODY_BYTES:
                        body_chunks.append(chunk)
                    else:
                        cacheable_body = False
                        body_chunks.clear()
            await send(message)

        await self.app(scope, _replay_receive(messages), send_wrapper)

        if 200 <= status_code < 300 and cacheable_body:
            body = b"".join(body_chunks)
            await redis_cache.set(
                cache_key,
                {
                    "request_hash": fingerprint,
                    "status": status_code,
                    "headers": [
                        [k, v]
                        for k, v in response_headers
                        if k.lower() not in _SENSITIVE_RESPONSE_HEADERS
                    ],
                    "body": body.decode("latin-1"),
                },
                ttl=self.ttl_seconds,
            )


async def _send_cached(send, cached: dict) -> None:
    headers = [
        (k.encode("latin-1"), v.encode("latin-1"))
        for k, v in cached.get("headers", [])
        if k.lower() not in _SENSITIVE_RESPONSE_HEADERS
    ]
    body = cached["body"].encode("latin-1")
    headers.append((b"idempotency-key-replayed", b"true"))
    headers.append((b"content-length", str(len(body)).encode("ascii")))

    await send({"type": "http.response.start", "status": cached["status"], "headers": headers})
    await send({"type": "http.response.body", "body": body})
