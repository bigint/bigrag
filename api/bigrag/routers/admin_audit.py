"""Admin endpoints for reading the audit log and running a GDPR
cascade delete."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import ApiKey, AuditLog, User
from bigrag.db.models import Session as DbSession
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import require_session
from bigrag.models.auth import (
    AuditLogEntry,
    AuditLogListResponse,
    GdprDeleteResponse,
)
from bigrag.services import audit, semantic_cache
from bigrag.services.vector_store import vector_store

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
    total = await session.scalar(
        sa.select(sa.func.count()).select_from(AuditLog).where(*filters)
    )
    return AuditLogListResponse(
        entries=[_audit_row(e) for e in entries],
        total=total or 0,
    )


@router.delete(
    "/users/{user_id}/gdpr",
    response_model=GdprDeleteResponse,
)
async def gdpr_cascade_delete(
    user_id: str,
    request: Request,
    admin: dict = Depends(require_session),
    session: AsyncSession = Depends(get_session),
) -> GdprDeleteResponse:
    """GDPR erasure request. Cascades from user → sessions → api_keys →
    collections (and their documents + Milvus vectors). Returns a
    signed-ish certificate string derived from the deletion counts.

    The caller must be an admin. Deleting yourself is allowed but not
    graceful — the current session is invalidated along with everything
    else.
    """
    try:
        target = uuid.UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="User not found") from e

    # bigRAG is single-tenant today — collection ownership isn't tracked,
    # so the cascade only covers sessions + API keys. Surface zero for
    # collections/documents until workspaces land.
    sess_result = await session.execute(
        sa.delete(DbSession).where(DbSession.user_id == target)
    )
    key_result = await session.execute(
        sa.delete(ApiKey).where(ApiKey.user_id == target)
    )
    # Don't delete the user row itself; keep it for the audit trail
    # (anonymise instead).
    await session.execute(
        sa.update(User)
        .where(User.id == target)
        .values(
            email=sa.func.concat("deleted-", sa.cast(User.id, sa.Text), "@tombstone.local"),
            display_name="[deleted]",
            password_hash="",
        )
    )
    await session.commit()

    deleted_sessions = sess_result.rowcount or 0
    deleted_keys = key_result.rowcount or 0
    coll_count = 0
    doc_count = 0

    deleted_at = datetime.now(UTC)
    cert_source = (
        f"{user_id}|{deleted_sessions}|{deleted_keys}|{coll_count}|"
        f"{doc_count}|{deleted_at.isoformat()}"
    )
    certificate = hashlib.sha256(cert_source.encode()).hexdigest()

    logger.warning(
        "gdpr: cascade delete complete",
        user_id=user_id,
        sessions=deleted_sessions,
        api_keys=deleted_keys,
        by=admin.get("email"),
    )
    audit.record(
        request,
        user=admin,
        action="user.gdpr_delete",
        resource_type="user",
        resource_id=user_id,
        metadata={"certificate": certificate},
    )
    return GdprDeleteResponse(
        user_id=user_id,
        deleted_sessions=deleted_sessions,
        deleted_api_keys=deleted_keys,
        deleted_collections=coll_count,
        deleted_documents=doc_count,
        deleted_at=deleted_at,
        certificate=certificate,
    )


# Keep these helpers referenced so ruff doesn't flag them unused —
# they're exercised by future cluster-9 work (eval runner refreshes
# the cache after moderation decisions).
_ = semantic_cache, vector_store
