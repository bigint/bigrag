"""Per-admin preferences — arbitrary JSON blob keyed on the user.

Used by the Studio to persist playground settings (OpenAI API key, chosen
model, top-K, temperature, system prompt) so they follow the admin across
browsers and devices instead of being stuck in localStorage.

Session-authenticated only: machine API keys don't have a persistent user,
so they can't read/write personal preferences.
"""

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

logger = get_logger("bigrag.routers.preferences")

router = APIRouter(prefix="/v1/auth/preferences", tags=["auth"])


@router.get("")
async def get_preferences(
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> dict:
    row = await session.scalar(
        sa.select(UserPreference).where(UserPreference.user_id == uuid.UUID(user["id"]))
    )
    return {"data": dict(row.data) if row else {}}


@router.put("")
async def update_preferences(
    body: dict,
    user: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Shallow-merge the request body into the stored preferences.

    Keys are overwritten; missing keys are preserved. Send an explicit ``null``
    to clear a single key.
    """
    incoming = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(incoming, dict):
        incoming = {}

    stmt = pg_insert(UserPreference).values(
        user_id=uuid.UUID(user["id"]), data=incoming
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[UserPreference.user_id],
        set_={
            "data": UserPreference.data.op("||")(stmt.excluded.data),
            "updated_at": sa.func.now(),
        },
    ).returning(UserPreference.data)
    result = await session.execute(stmt)
    await session.commit()
    return {"data": dict(result.scalar_one())}
