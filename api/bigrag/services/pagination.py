from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Any
from uuid import UUID

import orjson
import sqlalchemy as sa

from bigrag.exceptions import ValidationError


def encode_cursor(created_at: datetime, id_: UUID | str) -> str:
    payload = {"created_at": created_at.isoformat(), "id": str(id_)}
    raw = orjson.dumps(payload)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_cursor(token: str) -> tuple[datetime, str]:
    if not token:
        raise ValidationError("cursor is empty")
    padding = "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(token + padding)
        payload = orjson.loads(raw)
    except (binascii.Error, ValueError, orjson.JSONDecodeError) as exc:
        raise ValidationError("cursor is malformed") from exc
    if not isinstance(payload, dict):
        raise ValidationError("cursor is malformed")
    created_at_raw = payload.get("created_at")
    id_raw = payload.get("id")
    if not isinstance(created_at_raw, str) or not isinstance(id_raw, str):
        raise ValidationError("cursor is malformed")
    try:
        created_at = datetime.fromisoformat(created_at_raw)
    except ValueError as exc:
        raise ValidationError("cursor is malformed") from exc
    return created_at, id_raw


def apply_cursor(
    stmt: sa.sql.Select,
    created_col: sa.sql.ColumnElement,
    id_col: sa.sql.ColumnElement,
    cursor: tuple[datetime, str] | None,
    direction: str = "desc",
) -> sa.sql.Select:
    if cursor is None:
        return stmt
    created_at, id_ = cursor
    if direction == "desc":
        return stmt.where(
            sa.or_(
                created_col < created_at,
                sa.and_(created_col == created_at, id_col < id_),
            )
        )
    return stmt.where(
        sa.or_(
            created_col > created_at,
            sa.and_(created_col == created_at, id_col > id_),
        )
    )


def build_response_cursor(
    rows: list[Any],
    created_attr: str,
    id_attr: str,
    limit: int,
) -> tuple[list[Any], str | None]:
    if len(rows) <= limit:
        return rows, None
    page = rows[:limit]
    last = page[-1]
    next_token = encode_cursor(getattr(last, created_attr), getattr(last, id_attr))
    return page, next_token
