"""Per-admin preferences — arbitrary JSON blob keyed on the user.

Used by the Studio to persist playground settings (OpenAI API key, chosen
model, top-K, temperature, system prompt) so they follow the admin across
browsers and devices instead of being stuck in localStorage.

Session-authenticated only: machine API keys don't have a persistent user,
so they can't read/write personal preferences.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from bigrag.database import db
from bigrag.logging import get_logger
from bigrag.middleware.auth import require_session

logger = get_logger("bigrag.routers.preferences")

router = APIRouter(prefix="/v1/auth/preferences", tags=["auth"])


@router.get("")
async def get_preferences(user: dict = Depends(require_session)) -> dict:
    row = await db.fetchrow(
        "SELECT data FROM user_preferences WHERE user_id = $1",
        uuid.UUID(user["id"]),
    )
    return {"data": dict(row["data"]) if row else {}}


@router.put("")
async def update_preferences(
    body: dict,
    user: dict = Depends(require_session),
) -> dict:
    """Shallow-merge the request body into the stored preferences.

    Keys are overwritten; missing keys are preserved. Send an explicit ``null``
    to clear a single key.
    """
    incoming = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(incoming, dict):
        incoming = {}

    row = await db.fetchrow(
        """
        INSERT INTO user_preferences (user_id, data)
        VALUES ($1, $2)
        ON CONFLICT (user_id)
        DO UPDATE SET data = user_preferences.data || EXCLUDED.data,
                      updated_at = now()
        RETURNING data
        """,
        uuid.UUID(user["id"]),
        incoming,
    )
    return {"data": dict(row["data"])}
