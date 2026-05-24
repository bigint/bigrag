from __future__ import annotations

import base64
import uuid
from datetime import date, datetime
from typing import Any

from bigrag.services.backup.constants import REDACTED

_RESTORE_BATCH_SIZE = 500


class RestoreError(RuntimeError):
    pass


class RestoreNotEmptyError(RestoreError):
    pass


class RestoreChecksumError(RestoreError):
    pass


class RestoreRedactedError(RestoreError):
    pass


def _coerce_row(table: Any, columns: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for name, value in raw.items():
        column = columns.get(name)
        if column is None:
            continue
        if value == REDACTED:
            if not column.nullable:
                raise RestoreRedactedError(
                    f"Cannot restore redacted non-nullable column {table.name}.{name}; "
                    "this value was not captured in the backup"
                )
            row[name] = None
            continue
        row[name] = _coerce_value(column, value)
    return row


def _coerce_value(column: Any, value: Any) -> Any:
    if value is None:
        return None
    type_name = column.type.__class__.__name__
    if type_name in {"Uuid", "UUID"} and isinstance(value, str):
        return uuid.UUID(value)
    if type_name == "DateTime" and isinstance(value, str):
        return datetime.fromisoformat(value)
    if type_name == "Date" and isinstance(value, str):
        return date.fromisoformat(value)
    if type_name in {"LargeBinary", "BYTEA"} and isinstance(value, str):
        return base64.b64decode(value)
    return value
