from __future__ import annotations

import re

from qdrant_client import models

_SAFE_FIELD_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def validate_field(key: str) -> str:
    if not _SAFE_FIELD_RE.match(key):
        raise ValueError(f"Invalid filter field name: {key!r}")
    return key


def validate_scalar(val: object, op: str) -> None:
    if not isinstance(val, (str, int, float, bool)):
        raise ValueError(f"Filter operator {op} requires a scalar value, got {type(val).__name__}")


def _match_condition(field: str, value: str | int | float | bool) -> models.FieldCondition:
    return models.FieldCondition(key=field, match=models.MatchValue(value=value))


def build_filter(filters: dict) -> models.Filter | None:
    must: list[models.Condition] = []
    must_not: list[models.Condition] = []

    for key, value in filters.items():
        field = validate_field(key)
        if isinstance(value, (str, int, float, bool)):
            must.append(_match_condition(field, value))
        elif isinstance(value, dict):
            if not value:
                raise ValueError(f"Filter field {field!r} has no operators")
            for op, val in value.items():
                if op == "$eq":
                    validate_scalar(val, op)
                    must.append(_match_condition(field, val))
                elif op == "$ne":
                    validate_scalar(val, op)
                    must_not.append(_match_condition(field, val))
                elif op in ("$gt", "$gte", "$lt", "$lte"):
                    if not isinstance(val, (int, float)) or isinstance(val, bool):
                        raise ValueError(
                            f"Filter operator {op} requires a numeric value, "
                            f"got {type(val).__name__}"
                        )
                    must.append(
                        models.FieldCondition(
                            key=field,
                            range=models.Range(
                                gt=val if op == "$gt" else None,
                                gte=val if op == "$gte" else None,
                                lt=val if op == "$lt" else None,
                                lte=val if op == "$lte" else None,
                            ),
                        )
                    )
                elif op == "$in":
                    if not isinstance(val, list):
                        raise ValueError("Filter operator $in requires a list value")
                    for item in val:
                        validate_scalar(item, "$in")
                    must.append(
                        models.FieldCondition(
                            key=field,
                            match=models.MatchAny(any=val),
                        )
                    )
                else:
                    raise ValueError(f"Unsupported filter operator {op!r} for field {field!r}")
        else:
            raise ValueError(
                f"Filter field {field!r} requires a scalar value or operator object, "
                f"got {type(value).__name__}"
            )

    if not must and not must_not:
        return None
    return models.Filter(must=must or None, must_not=must_not or None)
