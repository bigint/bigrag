from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Scalar = str | int | float | bool
FilterOperator = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in"]

_SAFE_FIELD_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass(frozen=True)
class FilterCondition:
    field: str
    operator: FilterOperator
    value: Scalar | list[Scalar]


@dataclass(frozen=True)
class FilterExpression:
    conditions: tuple[FilterCondition, ...]


def validate_field(key: str) -> str:
    if not _SAFE_FIELD_RE.match(key):
        raise ValueError(f"Invalid filter field name: {key!r}")
    return key


def validate_scalar(val: object, op: str) -> None:
    if not isinstance(val, (str, int, float, bool)):
        raise ValueError(f"Filter operator {op} requires a scalar value, got {type(val).__name__}")


def build_filter(filters: dict) -> FilterExpression | None:
    conditions: list[FilterCondition] = []

    for key, value in filters.items():
        field = validate_field(key)
        if isinstance(value, (str, int, float, bool)):
            conditions.append(FilterCondition(field, "eq", value))
        elif isinstance(value, dict):
            if not value:
                raise ValueError(f"Filter field {field!r} has no operators")
            for op, val in value.items():
                if op == "$eq":
                    validate_scalar(val, op)
                    conditions.append(FilterCondition(field, "eq", val))
                elif op == "$ne":
                    validate_scalar(val, op)
                    conditions.append(FilterCondition(field, "ne", val))
                elif op in ("$gt", "$gte", "$lt", "$lte"):
                    if not isinstance(val, (int, float)) or isinstance(val, bool):
                        raise ValueError(
                            f"Filter operator {op} requires a numeric value, "
                            f"got {type(val).__name__}"
                        )
                    conditions.append(FilterCondition(field, op.removeprefix("$"), val))
                elif op == "$in":
                    if not isinstance(val, list):
                        raise ValueError("Filter operator $in requires a list value")
                    for item in val:
                        validate_scalar(item, "$in")
                    conditions.append(FilterCondition(field, "in", val))
                else:
                    raise ValueError(f"Unsupported filter operator {op!r} for field {field!r}")
        else:
            raise ValueError(
                f"Filter field {field!r} requires a scalar value or operator object, "
                f"got {type(value).__name__}"
            )

    if not conditions:
        return None
    return FilterExpression(tuple(conditions))
