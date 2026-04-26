from __future__ import annotations

import re

_SAFE_FIELD_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def validate_field(key: str) -> str:
    if not _SAFE_FIELD_RE.match(key):
        raise ValueError(f"Invalid filter field name: {key!r}")
    return key


def escape_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def validate_scalar(val: object, op: str) -> None:
    if not isinstance(val, (str, int, float, bool)):
        raise ValueError(f"Filter operator {op} requires a scalar value, got {type(val).__name__}")


def format_value(val: str | int | float | bool) -> str:
    if isinstance(val, str):
        return f'"{escape_string(val)}"'
    if isinstance(val, bool):
        return "true" if val else "false"
    return str(val)


def build_filter_expr(filters: dict) -> str | None:
    expressions = []

    for key, value in filters.items():
        field = validate_field(key)
        if isinstance(value, (str, int, float, bool)):
            expressions.append(f"{field} == {format_value(value)}")
        elif isinstance(value, dict):
            for op, val in value.items():
                if op in ("$eq", "$ne"):
                    validate_scalar(val, op)
                    sym = "==" if op == "$eq" else "!="
                    expressions.append(f"{field} {sym} {format_value(val)}")
                elif op in ("$gt", "$gte", "$lt", "$lte"):
                    if not isinstance(val, (int, float)):
                        raise ValueError(
                            f"Filter operator {op} requires a numeric value, "
                            f"got {type(val).__name__}"
                        )
                    op_map = {"$gt": ">", "$gte": ">=", "$lt": "<", "$lte": "<="}
                    expressions.append(f"{field} {op_map[op]} {val}")
                elif op == "$in":
                    if not isinstance(val, list):
                        raise ValueError("Filter operator $in requires a list value")
                    safe_vals = []
                    for v in val:
                        validate_scalar(v, "$in")
                        safe_vals.append(format_value(v))
                    expressions.append(f"{field} in [{', '.join(safe_vals)}]")

    return " and ".join(expressions) if expressions else None
