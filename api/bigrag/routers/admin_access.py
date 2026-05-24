from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.session import get_session
from bigrag.middleware.auth import require_admin_session
from bigrag.models.access import AccessLogListResponse, AccessLogOverviewResponse
from bigrag.services.access_log.queries import access_logs_payload, access_overview_payload

router = APIRouter(prefix="/v1/admin/access", tags=["admin:access"])


@router.get("/logs", response_model=AccessLogListResponse)
async def list_access_logs(
    action: str | None = Query(default=None, max_length=100),
    actor_id: str | None = Query(default=None),
    collection: str | None = Query(default=None, max_length=120),
    method: str | None = Query(default=None, max_length=10),
    path: str | None = Query(default=None, max_length=300),
    status_family: str | None = Query(default=None, pattern=r"^[1-5]xx$"),
    success: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = Query(default=None),
    include_total: bool = Query(default=False),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> AccessLogListResponse:
    return await access_logs_payload(
        session,
        action=action,
        actor_id=actor_id,
        collection=collection,
        method=method,
        path=path,
        status_family=status_family,
        success=success,
        limit=limit,
        offset=offset,
        cursor=cursor,
        include_total=include_total,
    )


@router.get("/overview", response_model=AccessLogOverviewResponse)
async def access_overview(
    window_days: int = Query(default=7, ge=1, le=90),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> AccessLogOverviewResponse:
    return await access_overview_payload(session, window_days=window_days)
