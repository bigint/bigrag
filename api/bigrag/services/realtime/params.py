from __future__ import annotations

import re
from typing import Any

from bigrag.services.realtime.specs import TopicError


def string(
    params: dict[str, Any],
    key: str,
    *,
    default: str | None = None,
    required: bool = False,
    max_length: int | None = None,
    pattern: re.Pattern[str] | None = None,
) -> str | None:
    value = params.get(key, default)
    if value is None or value == "":
        if required:
            raise TopicError(f"{key} is required")
        return None
    if not isinstance(value, str):
        raise TopicError(f"{key} must be a string")
    if max_length is not None and len(value) > max_length:
        raise TopicError(f"{key} is too long")
    if pattern is not None and not pattern.fullmatch(value):
        raise TopicError(f"{key} is invalid")
    return value


def integer(
    params: dict[str, Any],
    key: str,
    *,
    default: int,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    value = params.get(key, default)
    if isinstance(value, bool):
        raise TopicError(f"{key} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise TopicError(f"{key} must be an integer") from exc
    if minimum is not None and parsed < minimum:
        raise TopicError(f"{key} is too small")
    if maximum is not None and parsed > maximum:
        raise TopicError(f"{key} is too large")
    return parsed


def boolean(params: dict[str, Any], key: str) -> bool | None:
    value = params.get(key)
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
    raise TopicError(f"{key} must be a boolean")


def document_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, list):
        raw_values = [str(item) for item in value]
    else:
        raise TopicError("document_ids is required")
    parsed = [item.strip() for raw in raw_values for item in raw.split(",") if item.strip()]
    if not parsed:
        raise TopicError("document_ids is required")
    if len(parsed) > 100:
        raise TopicError("Maximum 100 documents per subscription")
    return parsed
