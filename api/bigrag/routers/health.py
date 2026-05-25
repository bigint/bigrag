from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import ORJSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag import __version__
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.services.health import readiness_status
from bigrag.services.platform_stats import platform_stats_payload

logger = get_logger("bigrag.routers.health")

router = APIRouter(tags=["health"])


@router.get("/health", response_model=dict[str, str])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/health/ready", response_model=dict[str, object])
async def readiness(request: Request) -> ORJSONResponse:
    checks, healthy = await readiness_status(
        request.app.state.vector_store,
        request.app.state.queue,
    )
    return ORJSONResponse(content=checks, status_code=200 if healthy else 503)


@router.get("/v1/stats", response_model=dict[str, object])
async def platform_stats(
    request: Request,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    return await platform_stats_payload(request.app.state.queue, session)
