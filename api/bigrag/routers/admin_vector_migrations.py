from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import VectorMigrationJob
from bigrag.db.session import get_session
from bigrag.middleware.auth import require_admin_session
from bigrag.models import StatusResponse
from bigrag.models.vector_migration import (
    VectorMigrationCreateRequest,
    VectorMigrationJobListResponse,
    VectorMigrationJobResponse,
)
from bigrag.routers import uuid_or_404
from bigrag.services import audit
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.jobs.actors import enqueue_vector_migration_job
from bigrag.services.pagination import apply_cursor, build_response_cursor, decode_cursor_or_400
from bigrag.services.vector_migration import (
    VectorMigrationConflictError,
    VectorMigrationError,
    create_vector_migration_job,
    delete_vector_migration_job,
)

router = APIRouter(
    prefix="/v1/admin/vector-storage/migrations",
    tags=["admin:vector-storage"],
)


def vector_migration_job_response(job: VectorMigrationJob) -> VectorMigrationJobResponse:
    return VectorMigrationJobResponse(
        id=str(job.id),
        collection_id=str(job.collection_id) if job.collection_id else None,
        collection_name=job.collection_name,
        source_provider=job.source_provider,
        target_provider=job.target_provider,
        status=job.status,
        phase=job.phase,
        progress=job.progress,
        copied_points=job.copied_points,
        total_points=job.total_points,
        details=job.details or {},
        error_message=job.error_message,
        created_by=str(job.created_by) if job.created_by else None,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("", response_model=VectorMigrationJobListResponse)
async def list_vector_migration_jobs(
    collection: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = Query(default=None),
    include_total: bool = Query(default=False),
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> VectorMigrationJobListResponse:
    cursor_tuple = decode_cursor_or_400(cursor)
    stmt = sa.select(VectorMigrationJob).order_by(
        VectorMigrationJob.created_at.desc(),
        VectorMigrationJob.id.desc(),
    )
    count_stmt = sa.select(sa.func.count()).select_from(VectorMigrationJob)
    if collection:
        stmt = stmt.where(VectorMigrationJob.collection_name == collection)
        count_stmt = count_stmt.where(VectorMigrationJob.collection_name == collection)

    if cursor_tuple is not None:
        stmt = apply_cursor(
            stmt,
            VectorMigrationJob.created_at,
            VectorMigrationJob.id,
            cursor_tuple,
        ).limit(limit + 1)
    else:
        stmt = stmt.limit(limit + 1).offset(offset)

    rows = (await session.scalars(stmt)).all()
    page, next_cursor = build_response_cursor(list(rows), "created_at", "id", limit)

    total: int | None = None
    if include_total:
        total = (await session.scalar(count_stmt)) or 0

    return VectorMigrationJobListResponse(
        jobs=[vector_migration_job_response(job) for job in page],
        total=total,
        next_cursor=next_cursor,
    )


@router.get("/{migration_id}", response_model=VectorMigrationJobResponse)
async def get_vector_migration_job(
    migration_id: str,
    _: dict = Depends(require_admin_session),
    session: AsyncSession = Depends(get_session),
) -> VectorMigrationJobResponse:
    try:
        target_id = UUID(migration_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid migration_id") from exc
    job = await session.get(VectorMigrationJob, target_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Vector migration job not found")
    return vector_migration_job_response(job)


@router.post("", response_model=VectorMigrationJobResponse, status_code=201)
async def start_vector_migration_job(
    body: VectorMigrationCreateRequest,
    request: Request,
    admin: dict = Depends(require_admin_session),
) -> VectorMigrationJobResponse:
    user_id = UUID(admin["id"]) if admin.get("id") else None
    try:
        job = await create_vector_migration_job(
            collection_name=body.collection,
            target_provider=body.target_provider,
            created_by=user_id,
        )
    except VectorMigrationConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=sanitize_message_text(str(exc)) or "Vector migration cannot be started.",
        ) from exc
    except VectorMigrationError as exc:
        raise HTTPException(
            status_code=400,
            detail=sanitize_message_text(str(exc)) or "Vector migration cannot be started.",
        ) from exc
    audit.record(
        request,
        user=admin,
        action="vector_migration.requested",
        resource_type="vector_migration_job",
        resource_id=str(job.id),
        metadata={
            "collection": job.collection_name,
            "source_provider": job.source_provider,
            "target_provider": job.target_provider,
        },
    )
    enqueue_vector_migration_job(str(job.id))
    return vector_migration_job_response(job)


@router.delete("/{migration_id}", response_model=StatusResponse)
async def delete_vector_migration_job_route(
    migration_id: str,
    request: Request,
    admin: dict = Depends(require_admin_session),
) -> StatusResponse:
    target_id = uuid_or_404(migration_id, "Vector migration job")
    result = await delete_vector_migration_job(target_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Vector migration job not found")
    audit.record(
        request,
        user=admin,
        action="vector_migration.delete",
        resource_type="vector_migration_job",
        resource_id=migration_id,
        metadata={"result": result},
    )
    if result == "stop_requested":
        return StatusResponse(status="ok", message="Vector migration stop requested")
    return StatusResponse(status="ok", message="Vector migration deleted")
