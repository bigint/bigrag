from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import BackupJob
from bigrag.models.backup import BackupJobListResponse, BackupJobResponse
from bigrag.services.pagination import paginate


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


async def backup_jobs_payload(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    cursor: str | None,
    include_total: bool,
) -> BackupJobListResponse:
    stmt = sa.select(BackupJob).order_by(BackupJob.created_at.desc(), BackupJob.id.desc())
    result = await paginate(
        session,
        stmt,
        created_col=BackupJob.created_at,
        id_col=BackupJob.id,
        cursor=cursor,
        limit=limit,
        offset=offset,
        count_stmt=(sa.select(sa.func.count()).select_from(BackupJob) if include_total else None),
    )
    return BackupJobListResponse(
        jobs=[backup_job_response(job) for job in result.rows],
        total=result.total,
        next_cursor=result.next_cursor,
    )
