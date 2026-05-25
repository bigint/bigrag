from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.session import get_session
from bigrag.middleware.auth import get_current_user, require_admin_session
from bigrag.models.access import AccessLogOverviewResponse
from bigrag.models.status import CollectionsStatusResponse, OverviewStatusResponse
from bigrag.services.access_log.queries import access_overview_payload
from bigrag.services.health import readiness_payload
from bigrag.services.platform_stats import platform_stats_payload
from bigrag.services.status import collections_status_payload
from bigrag.services.usage import UsageResponse, usage_payload

router = APIRouter(tags=["status"])


@router.get("/v1/status/overview", response_model=OverviewStatusResponse)
async def overview_status(
    request: Request,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OverviewStatusResponse:
    return OverviewStatusResponse(
        platform=await platform_stats_payload(request.app.state.queue, session),
        readiness=await readiness_payload(request.app.state.vector_store, request.app.state.queue),
    )


@router.get("/v1/status/collections", response_model=CollectionsStatusResponse)
async def collections_status(
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CollectionsStatusResponse:
    return await collections_status_payload(session)


@router.get("/v1/status/usage", response_model=UsageResponse)
async def usage_status(
    window_days: int = Query(default=30, ge=1, le=365),
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UsageResponse:
    return await usage_payload(session, window_days=window_days)


@router.get("/v1/admin/status/access", response_model=AccessLogOverviewResponse)
async def access_status(
    window_days: int = Query(default=7, ge=1, le=90),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> AccessLogOverviewResponse:
    return await access_overview_payload(session, window_days=window_days)
