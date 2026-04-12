from __future__ import annotations

import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import S3IngestJob
from bigrag.db.session import get_session
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models.common import StatusResponse
from bigrag.models.s3 import S3JobListResponse, S3JobResponse, UpdateS3JobRequest
from bigrag.routers import get_collection_or_404

logger = get_logger("bigrag.routers.s3_jobs")

router = APIRouter(prefix="/v1/collections/{collection_name}/s3-jobs", tags=["s3-jobs"])


def _job_response(job: S3IngestJob) -> S3JobResponse:
    return S3JobResponse(
        id=str(job.id),
        collection_name=job.collection_name,
        bucket=job.bucket,
        prefix=job.prefix,
        region=job.region,
        endpoint_url=job.endpoint_url,
        file_types=list(job.file_types or []),
        metadata=dict(job.meta or {}),
        status=job.status,
        total_found=job.total_found,
        total_ingested=job.total_ingested,
        total_skipped=job.total_skipped,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("", response_model=S3JobListResponse)
async def list_s3_jobs(
    collection_name: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)

    jobs = (
        await session.scalars(
            sa.select(S3IngestJob)
            .where(S3IngestJob.collection_id == collection["id"])
            .order_by(S3IngestJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    total = await session.scalar(
        sa.select(sa.func.count())
        .select_from(S3IngestJob)
        .where(S3IngestJob.collection_id == collection["id"])
    )

    return S3JobListResponse(
        jobs=[_job_response(j) for j in jobs],
        total=total or 0,
    )


@router.get("/{job_id}", response_model=S3JobResponse)
async def get_s3_job(
    collection_name: str,
    job_id: str,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)

    job = await session.scalar(
        sa.select(S3IngestJob)
        .where(S3IngestJob.id == uuid.UUID(job_id))
        .where(S3IngestJob.collection_id == collection["id"])
    )
    if job is None:
        raise HTTPException(status_code=404, detail="S3 ingest job not found")

    return _job_response(job)


@router.patch("/{job_id}", response_model=S3JobResponse)
async def update_s3_job(
    collection_name: str,
    job_id: str,
    body: UpdateS3JobRequest,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)

    job = await session.scalar(
        sa.select(S3IngestJob)
        .where(S3IngestJob.id == uuid.UUID(job_id))
        .where(S3IngestJob.collection_id == collection["id"])
    )
    if job is None:
        raise HTTPException(status_code=404, detail="S3 ingest job not found")

    if body.file_types is not None:
        job.file_types = body.file_types
    if body.metadata is not None:
        job.meta = body.metadata
    await session.commit()
    await session.refresh(job)

    return _job_response(job)


@router.post("/{job_id}/resync", response_model=StatusResponse)
async def resync_s3_job(
    collection_name: str,
    job_id: str,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)

    job = await session.scalar(
        sa.select(S3IngestJob)
        .where(S3IngestJob.id == uuid.UUID(job_id))
        .where(S3IngestJob.collection_id == collection["id"])
    )
    if job is None:
        raise HTTPException(status_code=404, detail="S3 ingest job not found")

    job.status = "pending"
    job.total_found = 0
    job.total_ingested = 0
    job.total_skipped = 0
    job.error_message = None
    await session.commit()
    await session.refresh(job)

    from bigrag.services.s3_ingest import _start_job, cancel_job

    await cancel_job(job_id)  # cancel and wait before restarting

    _start_job(
        {
            "id": job.id,
            "collection_id": job.collection_id,
            "collection_name": job.collection_name,
            "bucket": job.bucket,
            "prefix": job.prefix,
            "region": job.region,
            "endpoint_url": job.endpoint_url,
            "access_key": job.access_key,
            "secret_key": job.secret_key,
            "no_sign_request": job.no_sign_request,
            "metadata": job.meta or {},
            "file_types": job.file_types or [],
        }
    )

    return StatusResponse(status="ok", message="S3 ingest job re-syncing")


@router.delete("/{job_id}", response_model=StatusResponse)
async def delete_s3_job(
    collection_name: str,
    job_id: str,
    _: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    collection = await get_collection_or_404(collection_name)

    job = await session.scalar(
        sa.select(S3IngestJob)
        .where(S3IngestJob.id == uuid.UUID(job_id))
        .where(S3IngestJob.collection_id == collection["id"])
    )
    if job is None:
        raise HTTPException(status_code=404, detail="S3 ingest job not found")

    from bigrag.services.s3_ingest import cancel_job

    await cancel_job(job_id)
    await session.delete(job)
    await session.commit()

    return StatusResponse(status="ok", message="S3 ingest job deleted")
