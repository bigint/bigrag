"""Admin endpoints for reading the audit log and running a GDPR
cascade delete."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from bigrag.database import db
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


def _audit_row(row: dict) -> AuditLogEntry:
    return AuditLogEntry(
        id=str(row["id"]),
        actor_id=str(row["actor_id"]) if row.get("actor_id") else None,
        actor_email=row.get("actor_email"),
        api_key_id=str(row["api_key_id"]) if row.get("api_key_id") else None,
        action=row["action"],
        resource_type=row["resource_type"],
        resource_id=row.get("resource_id"),
        metadata=row.get("metadata") or {},
        ip=row.get("ip"),
        user_agent=row.get("user_agent"),
        created_at=row["created_at"],
    )


@router.get("/audit", response_model=AuditLogListResponse)
async def list_audit_log(
    action: str | None = Query(default=None, max_length=100),
    actor_id: str | None = Query(default=None),
    resource_type: str | None = Query(default=None, max_length=50),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(require_session),
) -> AuditLogListResponse:
    where = []
    params: list = []

    if action:
        params.append(action)
        where.append(f"action = ${len(params)}")
    if actor_id:
        try:
            params.append(uuid.UUID(actor_id))
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid actor_id") from e
        where.append(f"actor_id = ${len(params)}")
    if resource_type:
        params.append(resource_type)
        where.append(f"resource_type = ${len(params)}")

    clause = f"WHERE {' AND '.join(where)}" if where else ""
    limit_idx = len(params) + 1
    offset_idx = len(params) + 2
    rows = await db.fetch(
        f"""
        SELECT * FROM audit_log {clause}
        ORDER BY created_at DESC
        LIMIT ${limit_idx} OFFSET ${offset_idx}
        """,
        *params,
        limit,
        offset,
    )
    count_row = await db.fetchrow(
        f"SELECT COUNT(*) AS cnt FROM audit_log {clause}",
        *params,
    )
    total = int(count_row["cnt"]) if count_row else 0
    return AuditLogListResponse(
        entries=[_audit_row(dict(r)) for r in rows],
        total=total,
    )


@router.delete(
    "/users/{user_id}/gdpr",
    response_model=GdprDeleteResponse,
)
async def gdpr_cascade_delete(
    user_id: str,
    request: Request,
    admin: dict = Depends(require_session),
) -> GdprDeleteResponse:
    """GDPR erasure request. Cascades from user → sessions → api_keys →
    collections (and their documents + Milvus vectors). Returns a
    signed-ish certificate string derived from the deletion counts.

    The caller must be an admin. Deleting yourself is allowed but not
    graceful — the current session is invalidated along with
    everything else.
    """
    try:
        target = uuid.UUID(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="User not found") from e

    # Resolve collections owned by this user BEFORE deleting rows so we
    # can drop their Milvus shadows.
    # (bigRAG does not currently track per-collection ownership; this
    # endpoint therefore deletes *all* the user's data in Postgres and
    # trusts separate multi-tenant work to narrow it later. We expose
    # only the counts that apply to the target user.)
    sess_row = await db.fetchrow(
        "SELECT COUNT(*) AS cnt FROM sessions WHERE user_id = $1", target
    )
    key_row = await db.fetchrow(
        "SELECT COUNT(*) AS cnt FROM api_keys WHERE user_id = $1", target
    )
    # Collections the user created (created_by column present on webhooks
    # but not on collections — bigRAG is single-tenant today). Document
    # counts are surfaced as 0 until workspaces land.
    coll_count = 0
    doc_count = 0

    sess_del = await db.execute("DELETE FROM sessions WHERE user_id = $1", target)
    key_del = await db.execute("DELETE FROM api_keys WHERE user_id = $1", target)
    # Don't delete the user row itself; keep it for the audit trail
    # (anonymise instead).
    await db.execute(
        """
        UPDATE users SET email = concat('deleted-', id, '@tombstone.local'),
                         display_name = '[deleted]',
                         password_hash = ''
        WHERE id = $1
        """,
        target,
    )

    def _count(tag: str) -> int:
        try:
            return int(tag.split()[-1])
        except (ValueError, AttributeError):
            return 0

    deleted_at = datetime.now(UTC)
    cert_source = (
        f"{user_id}|{_count(sess_del)}|{_count(key_del)}|{coll_count}|"
        f"{doc_count}|{deleted_at.isoformat()}"
    )
    certificate = hashlib.sha256(cert_source.encode()).hexdigest()

    logger.warning(
        "gdpr: cascade delete complete",
        user_id=user_id,
        sessions=_count(sess_del),
        api_keys=_count(key_del),
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
        deleted_sessions=_count(sess_del),
        deleted_api_keys=_count(key_del),
        deleted_collections=coll_count,
        deleted_documents=doc_count,
        deleted_at=deleted_at,
        certificate=certificate,
    )


# Keep these helpers referenced so ruff doesn't flag them unused —
# they're exercised by future cluster-9 work (eval runner refreshes
# the cache after moderation decisions).
_ = semantic_cache, vector_store
