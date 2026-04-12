"""Minimal JSON-Schema validator for collection metadata.

Supports the subset we need for metadata constraints — no need to pull
in jsonschema for something this targeted. Enforces:

- ``type`` (string, number, integer, boolean, array, object)
- ``required`` (list of required top-level keys)
- ``properties`` (per-key type + enum + min/max length + pattern)
- ``enum`` at property level

Raises :class:`ValueError` with a human-readable message. The router
turns that into a 400.
"""

from __future__ import annotations

import re
from typing import Any

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def validate(metadata: dict, schema: dict | None) -> None:
    """Raise ValueError if ``metadata`` doesn't satisfy ``schema``."""
    if not schema:
        return
    if schema.get("type") and schema["type"] != "object":
        raise ValueError("Top-level metadata schema must have type=object")

    for key in schema.get("required", []) or []:
        if key not in metadata:
            raise ValueError(f"Metadata is missing required field: {key!r}")

    properties = schema.get("properties") or {}
    for key, spec in properties.items():
        if key not in metadata:
            continue
        value = metadata[key]
        _validate_property(key, value, spec)


def _validate_property(key: str, value: Any, spec: dict) -> None:
    type_ = spec.get("type")
    if type_:
        check = _TYPE_CHECKS.get(type_)
        if check is None:
            raise ValueError(f"Unknown schema type {type_!r} for field {key!r}")
        if not check(value):
            raise ValueError(
                f"Metadata field {key!r} must be {type_}, got {type(value).__name__}"
            )
    if "enum" in spec and value not in spec["enum"]:
        raise ValueError(
            f"Metadata field {key!r} must be one of {spec['enum']}, got {value!r}"
        )
    if "pattern" in spec and isinstance(value, str):
        if not re.fullmatch(spec["pattern"], value):
            raise ValueError(
                f"Metadata field {key!r} must match pattern {spec['pattern']!r}"
            )
    if "minLength" in spec and isinstance(value, str):
        if len(value) < spec["minLength"]:
            raise ValueError(
                f"Metadata field {key!r} must be at least {spec['minLength']} chars"
            )
    if "maxLength" in spec and isinstance(value, str):
        if len(value) > spec["maxLength"]:
            raise ValueError(
                f"Metadata field {key!r} must be at most {spec['maxLength']} chars"
            )
    if "minimum" in spec and isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < spec["minimum"]:
            raise ValueError(f"Metadata field {key!r} must be >= {spec['minimum']}")
    if "maximum" in spec and isinstance(value, (int, float)) and not isinstance(value, bool):
        if value > spec["maximum"]:
            raise ValueError(f"Metadata field {key!r} must be <= {spec['maximum']}")
