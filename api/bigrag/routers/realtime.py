from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection
from bigrag.db.session import get_session
from bigrag.middleware.auth import get_current_user
from bigrag.services.error_sanitize import safe_error_detail
from bigrag.services.realtime import RealtimeConnection
from bigrag.services.realtime.auth import connection_principal, cookie_origin_allowed
from bigrag.services.realtime_tokens import (
    REALTIME_TOKEN_TTL_SECONDS,
    create_realtime_token,
)

router = APIRouter(tags=["realtime"])


@router.websocket("/v1/realtime")
async def realtime_socket(websocket: WebSocket):
    if not await cookie_origin_allowed(websocket):
        await websocket.close(code=1008)
        return
    principal = await connection_principal(websocket)
    await websocket.accept()
    await RealtimeConnection(websocket, principal).run()


@router.post("/v1/collections/{name}/realtime-token", response_model=dict[str, str | int])
async def create_collection_realtime_token(
    name: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str | int]:
    exists = await session.scalar(sa.select(Collection.id).where(Collection.name == name))
    if exists is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    try:
        token = await create_realtime_token(user, name)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=safe_error_detail(exc, "Realtime tokens are unavailable; check Redis."),
        ) from exc
    return {"token": token, "expires_in": REALTIME_TOKEN_TTL_SECONDS}
