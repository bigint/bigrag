from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.services.usage import UsageResponse, usage_payload

logger = get_logger("bigrag.routers.usage")

router = APIRouter(prefix="/v1/usage", tags=["usage"])


@router.get("", response_model=UsageResponse)
async def get_usage(
    window_days: int = Query(default=30, ge=1, le=365),
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UsageResponse:
    return await usage_payload(session, window_days=window_days)
