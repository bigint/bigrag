from __future__ import annotations

import multiprocessing
import os
import re

WORKER_LOG_CONTEXT_ENV = "BIGRAG_WORKER_LOG_CONTEXT"


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
