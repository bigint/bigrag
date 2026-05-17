from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import UserPreference
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import require_session
from bigrag.services.preferences import (
    _deep_merge,
    _encrypt_sensitive,
    _normalize_sensitive,
    _public_preferences,
    _remove_cleared_sensitive,
    _validate_sensitive,
)

logger = get_logger("bigrag.routers.preferences")

router = APIRouter(prefix="/v1/auth/preferences", tags=["auth"])


@router.get("", response_model=dict[str, dict])
async def get_preferences(
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await session.scalar(
        sa.select(UserPreference).where(UserPreference.user_id == uuid.UUID(user["id"]))
    )
    return {"data": _public_preferences(dict(row.data)) if row else {}}


@router.put("", response_model=dict[str, dict])
async def update_preferences(
    body: dict,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> dict:

    incoming = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(incoming, dict):
        incoming = {}

    user_id = uuid.UUID(user["id"])
    existing_row = await session.scalar(
        sa.select(UserPreference).where(UserPreference.user_id == user_id)
    )
    existing = dict(existing_row.data) if existing_row else {}
    incoming = _normalize_sensitive(incoming)
    await _validate_sensitive(incoming)
    incoming = _encrypt_sensitive(incoming)
    merged = _remove_cleared_sensitive(_deep_merge(existing, incoming), incoming)

    stmt = pg_insert(UserPreference).values(user_id=user_id, data=merged)
    stmt = stmt.on_conflict_do_update(
        index_elements=[UserPreference.user_id],
        set_={
            "data": stmt.excluded.data,
            "updated_at": sa.func.now(),
        },
    ).returning(UserPreference.data)
    result = await session.execute(stmt)
    await session.commit()
    return {"data": _public_preferences(dict(result.scalar_one()))}
