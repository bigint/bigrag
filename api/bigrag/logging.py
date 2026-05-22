from __future__ import annotations

import logging
import multiprocessing
import os
import re
import sys

import structlog
from structlog.dev import Column, ConsoleRenderer, KeyValueColumnFormatter, LogLevelColumnFormatter

WORKER_LOG_CONTEXT_ENV = "BIGRAG_WORKER_LOG_CONTEXT"
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
        "x_api_key",
        "apikey",
        "api_secret_key",
        "secret_key",
        "credential",
        "credentials",
        "signature",
        "signing_secret",
        "webhook_secret",
        "secret",
        "master_key",
        "master_key_previous",
    }
)
_SENSITIVE_COMPACT_KEYS = frozenset(
    key.replace("_", "").replace("-", "") for key in _SENSITIVE_KEYS
)
_SENSITIVE_KEY_MARKERS = frozenset(
    {
        "api_key",
        "apikey",
        "access_key",
        "password",
        "secret",
        "credential",
        "signature",
    }
)
REQUEST_ID_HEADER = "x-request-id"
_MAX_LOG_VALUE_LENGTH = 2048
_CONTROL_CHAR_REPLACEMENTS = {
    "\n": r"\n",
    "\r": r"\r",
    "\t": r"\t",
    "\x1b": r"\x1b",
}


def is_sensitive_log_key(value: object) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    compact = re.sub(r"[^a-z0-9]+", "", lowered)
    return (
        lowered in _SENSITIVE_KEYS
        or normalized in _SENSITIVE_KEYS
        or compact in _SENSITIVE_COMPACT_KEYS
        or normalized.endswith("_token")
        or normalized.endswith("_secret")
        or compact.endswith("token")
        or compact.endswith("secret")
        or any(marker in normalized or marker in compact for marker in _SENSITIVE_KEY_MARKERS)
    )


def truncate_log_value(value: str) -> str:
    if len(value) <= _MAX_LOG_VALUE_LENGTH:
        return value
    return f"{value[:_MAX_LOG_VALUE_LENGTH]}..."


def _escape_control_characters(value: str) -> str:
    return "".join(
        _CONTROL_CHAR_REPLACEMENTS.get(char)
        or (f"\\x{ord(char):02x}" if ord(char) < 32 or 127 <= ord(char) <= 159 else char)
        for char in value
    )


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


def shorten_logger_name(_logger, _method_name, event_dict):
    value = event_dict.get("logger")
    if isinstance(value, str):
        for prefix in (
            "bigrag.services.",
            "bigrag.routers.",
            "bigrag.middleware.",
            "bigrag.app_factory.",
            "bigrag.",
            "dramatiq.",
            "uvicorn.",
        ):
            if value.startswith(prefix):
                value = value.removeprefix(prefix)
                break
        event_dict["logger"] = f"...{value[-29:]}" if len(value) > 32 else value
    return event_dict


def hide_terminal_context(_logger, _method_name, event_dict):
    event_dict.pop("request_id", None)
    return event_dict


def current_worker_label() -> str:
    process_name = multiprocessing.current_process().name
    if process_name != "MainProcess":
        match = re.search(r"(\d+)$", process_name)
        if match:
            return f"worker-{match.group(1)}"
        return process_name
    return "worker-parent"


def add_worker_context(_logger, _method_name, event_dict):
    if os.environ.get(WORKER_LOG_CONTEXT_ENV) != "1":
        return event_dict
    event_dict.setdefault("worker", current_worker_label())
    event_dict.setdefault("pid", os.getpid())
    return event_dict


def compact_terminal_event(_logger, _method_name, event_dict):
    event = event_dict.get("event")
    if event not in {"request_complete", "request_failed"}:
        return event_dict
    method = event_dict.get("method")
    path = event_dict.get("path")
    status = event_dict.get("status")
    elapsed_ms = event_dict.get("elapsed_ms")
    if method and path and status is not None and elapsed_ms is not None:
        suffix = " failed" if event == "request_failed" else ""
        event_dict["event"] = f"{method} {path} -> {status} in {elapsed_ms:.0f}ms{suffix}"
    for key in tuple(event_dict):
        if key not in {"event", "level", "logger"}:
            event_dict.pop(key, None)
    return event_dict


def _field_value(value: object) -> str:
    return truncate_log_value(_escape_control_characters(str(value)))


def _console_renderer() -> ConsoleRenderer:
    styles = ConsoleRenderer.get_default_column_styles(True, True)
    level_styles = ConsoleRenderer.get_default_level_styles(True)
    level_styles = {key: value + styles.bright for key, value in level_styles.items()}
    return ConsoleRenderer(
        sort_keys=False,
        columns=[
            Column(
                "timestamp",
                KeyValueColumnFormatter(
                    key_style=None,
                    value_style=styles.timestamp,
                    reset_style=styles.reset,
                    value_repr=str,
                    width=8,
                ),
            ),
            Column(
                "level",
                LogLevelColumnFormatter(level_styles, reset_style=styles.reset, width=0),
            ),
            Column(
                "logger",
                KeyValueColumnFormatter(
                    key_style=None,
                    value_style=styles.logger_name,
                    reset_style=styles.reset,
                    value_repr=str,
                    width=22,
                ),
            ),
            Column(
                "event",
                KeyValueColumnFormatter(
                    key_style=None,
                    value_style=styles.bright,
                    reset_style=styles.reset,
                    value_repr=_field_value,
                    width=30,
                ),
            ),
            Column(
                "",
                KeyValueColumnFormatter(
                    key_style=styles.kv_key,
                    value_style=styles.kv_value,
                    reset_style=styles.reset,
                    value_repr=_field_value,
                ),
            ),
        ],
    )


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
        renderer = _console_renderer()

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
