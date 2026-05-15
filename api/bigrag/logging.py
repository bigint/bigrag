from __future__ import annotations

import logging
import sys
import time
import uuid

import structlog
from starlette.datastructures import MutableHeaders

_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "embedding_api_key",
        "rerank_api_key",
        "reranking_api_key",
        "password",
        "password_hash",
        "session_token",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "signing_secret",
        "webhook_secret",
        "secret",
        "master_key",
        "master_key_previous",
    }
)
REQUEST_ID_HEADER = "x-request-id"
_REQUEST_ID_HEADER_BYTES = REQUEST_ID_HEADER.encode()


def _redact(value: object) -> object:
    if isinstance(value, dict):
        return {
            k: ("[REDACTED]" if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_redact(v) for v in value)
    return value


def redact_secrets(_logger, _method_name, event_dict):

    return _redact(event_dict)


def configure_logging(log_level: str = "debug", log_format: str = "text") -> None:

    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        redact_secrets,
        structlog.processors.TimeStamper(fmt="%H:%M:%S" if log_format == "text" else "iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=sys.stderr.isatty(),
            pad_event_to=32,
        )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    noisy_dependency_level = logging.INFO if level <= logging.DEBUG else logging.WARNING
    for name in ("qdrant_client", "httpx", "uvicorn.access"):
        logging.getLogger(name).setLevel(noisy_dependency_level)
    for name in ("httpcore", "hpack"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:

    return structlog.get_logger(name)


def _clean_request_id(value: str | None) -> str:
    cleaned = (value or "").strip().replace("\r", "").replace("\n", "")
    return cleaned[:128] if cleaned else uuid.uuid4().hex


def _request_id_from_scope(scope) -> str:
    for name, value in scope.get("headers", []):
        if name.lower() == _REQUEST_ID_HEADER_BYTES:
            return _clean_request_id(value.decode("latin-1", errors="ignore"))
    return _clean_request_id(None)


class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app
        self._logger = get_logger("bigrag.http")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        method = scope["method"]
        path = scope["path"]
        request_id = _request_id_from_scope(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        status_code = 0
        self._logger.info("request_start", method=method, path=path, request_id=request_id)

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", [])
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        await self.app(scope, receive, send_wrapper)
        elapsed_ms = (time.monotonic() - start) * 1000

        self._logger.info(
            "request",
            method=method,
            path=path,
            status=status_code,
            elapsed_ms=round(elapsed_ms, 1),
            request_id=request_id,
        )
