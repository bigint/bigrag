from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import AuditLog
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import require_session
from bigrag.models.auth import AuditLogEntry, AuditLogListResponse

logger = get_logger("bigrag.routers.admin_audit")

router = APIRouter(prefix="/v1/admin", tags=["admin:audit"])


def _audit_row(entry: AuditLog) -> AuditLogEntry:
    return AuditLogEntry(
        id=str(entry.id),
        actor_id=str(entry.actor_id) if entry.actor_id else None,
        actor_email=entry.actor_email,
        api_key_id=str(entry.api_key_id) if entry.api_key_id else None,
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        metadata=entry.meta or {},
        ip=entry.ip,
        user_agent=entry.user_agent,
        created_at=entry.created_at,
    )


@router.get("/audit", response_model=AuditLogListResponse)
async def list_audit_log(
    action: str | None = Query(default=None, max_length=100),
    actor_id: str | None = Query(default=None),
    resource_type: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> AuditLogListResponse:
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if actor_id:
        try:
            filters.append(AuditLog.actor_id == uuid.UUID(actor_id))
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid actor_id") from e
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)

    entries = (
        await session.scalars(
            sa.select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    total = await session.scalar(sa.select(sa.func.count()).select_from(AuditLog).where(*filters))
    return AuditLogListResponse(
        entries=[_audit_row(e) for e in entries],
        total=total or 0,
    )
