from __future__ import annotations

import logging
import sys

import structlog

_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "client_secret",
        "code",
        "csrf",
        "csrf_token",
        "embedding_api_key",
        "id_token",
        "rerank_api_key",
        "reranking_api_key",
        "oauth_token",
        "password",
        "password_hash",
        "proxy-authorization",
        "session_token",
        "state",
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
_MAX_LOG_VALUE_LENGTH = 2048


def is_sensitive_log_key(value: object) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    normalized = lowered.replace("-", "_")
    return (
        lowered in _SENSITIVE_KEYS
        or normalized in _SENSITIVE_KEYS
        or normalized.endswith("_token")
        or normalized.endswith("_secret")
        or "password" in normalized
    )


def truncate_log_value(value: str) -> str:
    if len(value) <= _MAX_LOG_VALUE_LENGTH:
        return value
    return f"{value[:_MAX_LOG_VALUE_LENGTH]}..."


def _redact(value: object) -> object:
    if isinstance(value, dict):
        return {
            k: ("[REDACTED]" if is_sensitive_log_key(k) else _redact(v)) for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_redact(v) for v in value)
    if isinstance(value, str):
        return truncate_log_value(value)
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
            colors=True,
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
