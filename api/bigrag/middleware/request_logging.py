from __future__ import annotations

import time
import uuid
from urllib.parse import parse_qsl

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import Receive, Scope, Send

from bigrag.logging import (
    REQUEST_ID_HEADER,
    get_logger,
    is_sensitive_log_key,
    safe_url_value,
    truncate_log_value,
)

_REQUEST_ID_HEADER_BYTES = REQUEST_ID_HEADER.encode()


def _clean_request_id(value: str | None) -> str:
    cleaned = (value or "").strip().replace("\r", "").replace("\n", "")
    return cleaned[:128] if cleaned else uuid.uuid4().hex


def _request_id_from_scope(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name.lower() == _REQUEST_ID_HEADER_BYTES:
            return _clean_request_id(value.decode("latin-1", errors="ignore"))
    return _clean_request_id(None)


def _safe_url(value: str) -> str:
    return safe_url_value(value)


def _safe_value(key: str, value: str) -> str:
    if is_sensitive_log_key(key):
        return "[REDACTED]"
    if key.lower() in {"referer", "referrer"} or "://" in value:
        return _safe_url(value)
    return truncate_log_value(value)


def _multi_value_set(target: dict[str, object], key: str, value: str) -> None:
    existing = target.get(key)
    if existing is None:
        target[key] = value
    elif isinstance(existing, list):
        existing.append(value)
    else:
        target[key] = [existing, value]


def _header_from_scope(scope: Scope, target: str) -> str | None:
    wanted = target.lower().encode()
    for raw_name, raw_value in scope.get("headers", []):
        if raw_name.lower() == wanted:
            return raw_value.decode("latin-1", errors="replace")
    return None


def _query_from_scope(scope: Scope) -> dict[str, object]:
    raw_query = scope.get("query_string") or b""
    query: dict[str, object] = {}
    for key, value in parse_qsl(
        raw_query.decode("latin-1", errors="replace"),
        keep_blank_values=True,
    ):
        _multi_value_set(query, key, _safe_value(key, value))
    return query


def _client_ip_from_scope(scope: Scope) -> str | None:
    client = scope.get("client")
    return client[0] if client else None


def _route_path(scope: Scope) -> str | None:
    route = scope.get("route")
    return getattr(route, "path", None)


def _endpoint_name(scope: Scope) -> str | None:
    endpoint = scope.get("endpoint")
    return getattr(endpoint, "__name__", None) if endpoint is not None else None


def _state_value(scope: Scope, key: str) -> object:
    state = scope.get("state") or {}
    return state.get(key)


def _access_context(scope: Scope) -> dict[str, object]:
    context = _state_value(scope, "access_log_context")
    return dict(context) if isinstance(context, dict) else {}


def _request_start_fields(
    scope: Scope, method: str, path: str, request_id: str
) -> dict[str, object]:
    fields: dict[str, object] = {
        "request_id": request_id,
        "method": method,
        "path": path,
        "client_ip": _client_ip_from_scope(scope),
    }
    query = _query_from_scope(scope)
    if query:
        fields["query"] = query
    for header, key in (
        ("host", "host"),
        ("user-agent", "user_agent"),
        ("content-type", "content_type"),
        ("content-length", "content_length"),
        ("referer", "referer"),
    ):
        value = _header_from_scope(scope, header)
        if value:
            fields[key] = _safe_value(header, value)
    return fields


def _request_complete_fields(
    scope: Scope,
    method: str,
    path: str,
    request_id: str,
    status_code: int,
    elapsed_ms: float,
    first_byte_ms: float | None,
) -> dict[str, object]:
    context = _access_context(scope)
    return {
        "request_id": request_id,
        "method": method,
        "path": path,
        "route": _route_path(scope),
        "endpoint": _endpoint_name(scope),
        "action": context.get("action") or _endpoint_name(scope),
        "resource_type": context.get("resource_type"),
        "resource_id": context.get("resource_id"),
        "collection": context.get("collection_name"),
        "status": status_code,
        "elapsed_ms": round(elapsed_ms, 2),
        "first_byte_ms": round(first_byte_ms, 2) if first_byte_ms is not None else None,
    }


class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app
        self._logger = get_logger("bigrag.http")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        method = str(scope.get("method") or "")
        path = str(scope.get("path") or "")
        request_id = _request_id_from_scope(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        status_code = 500
        first_byte_ms: float | None = None
        context_tokens = structlog.contextvars.bind_contextvars(request_id=request_id)
        self._logger.debug(
            "request_start", **_request_start_fields(scope, method, path, request_id)
        )

        async def send_wrapper(message):
            nonlocal status_code, first_byte_ms
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                first_byte_ms = (time.monotonic() - start) * 1000
                message.setdefault("headers", [])
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
                self._logger.debug(
                    "response_start",
                    request_id=request_id,
                    method=method,
                    path=path,
                    route=_route_path(scope),
                    endpoint=_endpoint_name(scope),
                    status=status_code,
                    first_byte_ms=round(first_byte_ms, 2),
                )
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._logger.exception(
                "request_failed",
                **_request_complete_fields(
                    scope,
                    method,
                    path,
                    request_id,
                    status_code,
                    elapsed_ms,
                    first_byte_ms,
                ),
                error_type=exc.__class__.__name__,
            )
            raise
        else:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._logger.info(
                "request_complete",
                **_request_complete_fields(
                    scope,
                    method,
                    path,
                    request_id,
                    status_code,
                    elapsed_ms,
                    first_byte_ms,
                ),
            )
        finally:
            structlog.contextvars.reset_contextvars(**context_tokens)
