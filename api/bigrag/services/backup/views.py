from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import BackupJob
from bigrag.models.backup import BackupJobListResponse, BackupJobResponse
from bigrag.services.pagination import apply_cursor, build_response_cursor, decode_cursor_or_400


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
