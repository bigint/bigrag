from __future__ import annotations

import logging
import sys

import structlog

from bigrag.logging_redaction import (
    is_sensitive_log_key,
    redact_secrets,
    safe_url_value,
    truncate_log_value,
)
from bigrag.logging_rendering import console_renderer
from bigrag.logging_terminal import (
    WORKER_LOG_CONTEXT_ENV,
    add_worker_context,
    compact_terminal_event,
    current_worker_label,
    hide_terminal_context,
    shorten_logger_name,
)

REQUEST_ID_HEADER = "x-request-id"

__all__ = [
    "REQUEST_ID_HEADER",
    "WORKER_LOG_CONTEXT_ENV",
    "configure_logging",
    "current_worker_label",
    "get_logger",
    "is_sensitive_log_key",
    "safe_url_value",
    "truncate_log_value",
]


def configure_logging(log_level: str = "info", log_format: str = "text") -> None:

    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
    ]
    if log_format == "text":
        shared_processors.append(shorten_logger_name)
        shared_processors.append(compact_terminal_event)
        shared_processors.append(hide_terminal_context)
    shared_processors.append(add_worker_context)
    shared_processors.extend(
        [
            redact_secrets,
            structlog.processors.TimeStamper(fmt="%H:%M:%S" if log_format == "text" else "iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
        ]
    )

    if log_format == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = console_renderer()

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

    for name in (
        "alembic",
        "asyncio",
        "dramatiq",
        "hpack",
        "httpcore",
        "httpx",
        "openai",
        "openai._base_client",
        "uvicorn.access",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:

    return structlog.get_logger(name)
