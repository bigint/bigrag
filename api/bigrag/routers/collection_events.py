from __future__ import annotations

import asyncio

import orjson
import sqlalchemy as sa
from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from bigrag.db.models import Collection
from bigrag.db.session import get_session
from bigrag.middleware.auth import get_current_user
from bigrag.routers.collections import router
from bigrag.services.error_sanitize import safe_error_detail
from bigrag.services.event_bus import event_bus
from bigrag.services.event_tokens import (
    EVENT_TOKEN_TTL_SECONDS,
    create_event_token,
    validate_event_token,
)


@router.get("/{name}/events", response_class=StreamingResponse)
async def collection_events_sse(
    name: str,
    request: Request,
    token: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    if not await validate_event_token(token, name):
        await get_current_user(request)

    exists = await session.scalar(sa.select(Collection.id).where(Collection.name == name))
    if exists is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    async def generate():
        yield (
            f'data: {{"step":"connected","status":"connected",'
            f'"message":"Listening for events on {name}","progress":0}}\n\n'
        )

        key = f"collection:{name}"
        q = event_bus.subscribe(key)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                except TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                if event is None:
                    break
                data = {
                    "document_id": event.document_id,
                    "step": event.step,
                    "status": event.status,
                    "message": event.message,
                    "progress": event.progress,
                    **event.detail,
                }
                yield f"data: {orjson.dumps(data).decode()}\n\n"
        finally:
            event_bus.unsubscribe(key, q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{name}/events/token", response_model=dict[str, str | int])
async def create_collection_event_token(
    name: str,
    user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str | int]:
    exists = await session.scalar(sa.select(Collection.id).where(Collection.name == name))
    if exists is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    try:
        token = await create_event_token(user, name)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=safe_error_detail(exc, "Event tokens are unavailable; check Redis."),
        ) from exc
    return {"token": token, "expires_in": EVENT_TOKEN_TTL_SECONDS}
