from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import BackupJob
from bigrag.db.session import get_session
from bigrag.middleware.auth import require_admin_session
from bigrag.models.backup import BackupCreateRequest, BackupJobListResponse, BackupJobResponse
from bigrag.services import audit
from bigrag.services.backup import BackupConfigError, create_backup_job
from bigrag.services.backup.views import backup_job_response, backup_jobs_payload
from bigrag.services.error_sanitize import safe_error_detail
from bigrag.services.jobs.actors import enqueue_backup_job

router = APIRouter(prefix="/v1/admin/backups", tags=["admin:backups"])


@router.get("", response_model=BackupJobListResponse)
async def list_backup_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = Query(default=None),
    include_total: bool = Query(default=False),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> BackupJobListResponse:
    return await backup_jobs_payload(
        session,
        limit=limit,
        offset=offset,
        cursor=cursor,
        include_total=include_total,
    )


@router.get("/{backup_id}", response_model=BackupJobResponse)
async def get_backup_job(
    backup_id: str,
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> BackupJobResponse:
    try:
        target_id = UUID(backup_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid backup_id") from exc
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
