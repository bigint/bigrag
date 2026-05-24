from __future__ import annotations

import json
import math
import uuid
from datetime import date, datetime
from typing import Any

_JSON_PREFIX = "__bigrag_json_v1__:"
_RAW_FIELDS = {"vector"}


def encode_attributes(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value if key in _RAW_FIELDS else encode_attribute(value)
        for key, value in row.items()
        if value is not None
    }


def decode_attributes(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value if key in _RAW_FIELDS else decode_attribute(value) for key, value in row.items()
    }


def encode_attribute(value: Any) -> Any:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, dict | list | tuple):
        return _JSON_PREFIX + json.dumps(
            value,
            default=_json_default,
            separators=(",", ":"),
            sort_keys=True,
        )
    if isinstance(value, datetime | date | uuid.UUID):
        return str(_json_default(value))
    return str(value)


def decode_attribute(value: Any) -> Any:
    if not isinstance(value, str) or not value.startswith(_JSON_PREFIX):
        return value
    try:
        return json.loads(value[len(_JSON_PREFIX) :])
    except json.JSONDecodeError:
        return value


def _json_default(value: Any) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)
