from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import require_admin_session
from bigrag.models.auth import AuditLogListResponse
from bigrag.services.audit import audit_log_payload

logger = get_logger("bigrag.routers.admin_audit")

router = APIRouter(prefix="/v1/admin", tags=["admin:audit"])


@router.get("/audit", response_model=AuditLogListResponse)
async def list_audit_log(
    action: str | None = Query(default=None, max_length=100),
    actor_id: str | None = Query(default=None),
    resource_type: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = Query(default=None),
    include_total: bool = Query(default=False),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> AuditLogListResponse:
    return await audit_log_payload(
        session,
        action=action,
        actor_id=actor_id,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
        cursor=cursor,
        include_total=include_total,
    )
