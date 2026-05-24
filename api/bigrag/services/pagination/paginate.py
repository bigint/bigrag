from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.services.pagination.cursor import (
    apply_cursor,
    build_response_cursor,
    decode_cursor_or_400,
)


@dataclass
class Page:
    rows: list[Any]
    next_cursor: str | None
    total: int | None


async def paginate(
    session: AsyncSession,
    stmt,
    *,
    created_col,
    id_col,
    cursor: str | None,
    limit: int,
    offset: int,
    count_stmt=None,
    direction: str = "desc",
) -> Page:
    cursor_tuple = decode_cursor_or_400(cursor)
    if cursor_tuple is not None:
        stmt = apply_cursor(stmt, created_col, id_col, cursor_tuple, direction=direction).limit(
            limit + 1
        )
    else:
        stmt = stmt.limit(limit + 1).offset(offset)
    rows = (await session.scalars(stmt)).all()
    page, next_cursor = build_response_cursor(list(rows), "created_at", "id", limit)
    total = ((await session.scalar(count_stmt)) or 0) if count_stmt is not None else None
    return Page(rows=page, next_cursor=next_cursor, total=total)
