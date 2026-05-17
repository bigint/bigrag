from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import BackupJob
from bigrag.db.session import get_session
from bigrag.middleware.auth import require_admin_session
from bigrag.models.backup import BackupCreateRequest, BackupJobListResponse, BackupJobResponse
from bigrag.routers import uuid_or_404
from bigrag.services import audit
from bigrag.services.backup import BackupConfigError, create_backup_job
from bigrag.services.error_sanitize import safe_error_detail
from bigrag.services.jobs.actors import enqueue_backup_job
from bigrag.services.pagination import apply_cursor, build_response_cursor, decode_cursor_or_400

router = APIRouter(prefix="/v1/admin/backups", tags=["admin:backups"])


def backup_job_response(job: BackupJob) -> BackupJobResponse:
    return BackupJobResponse(
        id=str(job.id),
        label=job.label,
        status=job.status,
        progress=job.progress,
        destination_prefix=job.destination_prefix,
        object_count=job.object_count,
        byte_count=job.byte_count,
        manifest=job.manifest or {},
        error_message=job.error_message,
        created_by=str(job.created_by) if job.created_by else None,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("", response_model=BackupJobListResponse)
async def list_backup_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = Query(default=None),
    include_total: bool = Query(default=False),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> BackupJobListResponse:
    cursor_tuple = decode_cursor_or_400(cursor)

    stmt = sa.select(BackupJob).order_by(BackupJob.created_at.desc(), BackupJob.id.desc())
    if cursor_tuple is not None:
        stmt = apply_cursor(stmt, BackupJob.created_at, BackupJob.id, cursor_tuple).limit(limit + 1)
    else:
        stmt = stmt.limit(limit + 1).offset(offset)

    rows = (await session.scalars(stmt)).all()
    page, next_cursor = build_response_cursor(list(rows), "created_at", "id", limit)

    total: int | None = None
    if include_total:
        total = (await session.scalar(sa.select(sa.func.count()).select_from(BackupJob))) or 0
    return BackupJobListResponse(
        jobs=[backup_job_response(job) for job in page],
        total=total,
        next_cursor=next_cursor,
    )


@router.get("/{backup_id}", response_model=BackupJobResponse)
async def get_backup_job(
    backup_id: str,
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> BackupJobResponse:
    target_id = uuid_or_404(backup_id, "Backup job")
    job = await session.get(BackupJob, target_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Backup job not found")
    return backup_job_response(job)


@router.post("", response_model=BackupJobResponse, status_code=201)
async def start_backup_job(
    body: BackupCreateRequest,
    request: Request,
    admin: dict = Depends(require_admin_session),
) -> BackupJobResponse:
    user_id = UUID(admin["id"]) if admin.get("id") else None
    try:
        job = await create_backup_job(label=body.label, created_by=user_id)
    except BackupConfigError as exc:
        raise HTTPException(
            status_code=409, detail=safe_error_detail(exc, "Backup is not configured.")
        ) from exc
    audit.record(
        request,
        user=admin,
        action="backup.requested",
        resource_type="backup_job",
        resource_id=str(job.id),
        metadata={"label": job.label},
    )
    enqueue_backup_job(str(job.id))
    return backup_job_response(job)
