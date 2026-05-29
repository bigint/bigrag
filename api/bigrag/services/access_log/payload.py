from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from bigrag.logging import safe_url_value

_MAX_METADATA_DEPTH = 4
_MAX_METADATA_ITEMS = 32
_MAX_STRING_LEN = 300
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "cookie",
        "password",
        "prompt",
        "query",
        "secret",
        "session",
        "token",
    }
)


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        if "://" in value:
            return safe_url_value(value)
        if len(value) <= _MAX_STRING_LEN:
            return value
        return f"{value[:_MAX_STRING_LEN]}..."
    return str(value)[:_MAX_STRING_LEN]


def _safe_metadata(value: Any, *, depth: int = 0) -> Any:
    if depth >= _MAX_METADATA_DEPTH:
        return "[truncated]"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for idx, (key, item) in enumerate(value.items()):
            if idx >= _MAX_METADATA_ITEMS:
                result["_truncated"] = True
                break
            key_str = str(key)[:80]
            if key_str.lower() in _SENSITIVE_KEYS:
                result[key_str] = "[REDACTED]"
            else:
                result[key_str] = _safe_metadata(item, depth=depth + 1)
        return result
    if isinstance(value, list | tuple | set):
        items = list(value)
        result = [_safe_metadata(item, depth=depth + 1) for item in items[:_MAX_METADATA_ITEMS]]
        if len(items) > _MAX_METADATA_ITEMS:
            result.append("[truncated]")
        return result
    return _safe_scalar(value)


def query_fingerprint(query: str) -> dict[str, int | str]:
    return {
        "query_hash": hashlib.sha256(query.encode("utf-8")).hexdigest()[:24],
        "query_length": len(query),
    }


def filter_summary(filters: dict | None) -> dict[str, Any]:
    if not filters:
        return {"has_filters": False, "filter_keys": []}
    return {
        "has_filters": True,
        "filter_keys": sorted(str(key) for key in filters.keys())[:20],
    }
