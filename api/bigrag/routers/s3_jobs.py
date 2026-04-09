from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from bigrag.database import db
from bigrag.logging import get_logger
from bigrag.middleware.auth import get_current_user
from bigrag.models.document import S3JobListResponse, S3JobResponse
from bigrag.routers import get_collection_or_404

logger = get_logger("bigrag.routers.s3_jobs")

router = APIRouter(prefix="/v1/collections/{collection_name}/s3-jobs", tags=["s3-jobs"])


def _row_to_response(row: dict) -> S3JobResponse:
    r = {}
    for k, v in row.items():
        if isinstance(v, uuid.UUID):
            r[k] = str(v)
        else:
            r[k] = v
    return S3JobResponse(**r)


@router.get("", response_model=S3JobListResponse)
async def list_s3_jobs(
    collection_name: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)

    rows = await db.fetch(
        """
        SELECT * FROM s3_ingest_jobs
        WHERE collection_id = $1
        ORDER BY created_at DESC LIMIT $2 OFFSET $3
        """,
        collection["id"],
        limit,
        offset,
    )
    count_row = await db.fetchrow(
        "SELECT COUNT(*) as cnt FROM s3_ingest_jobs WHERE collection_id = $1",
        collection["id"],
    )

    return S3JobListResponse(
        jobs=[_row_to_response(dict(r)) for r in rows],
        total=count_row["cnt"],
    )


@router.get("/{job_id}", response_model=S3JobResponse)
async def get_s3_job(
    collection_name: str,
    job_id: str,
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)

    row = await db.fetchrow(
        "SELECT * FROM s3_ingest_jobs WHERE id = $1 AND collection_id = $2",
        uuid.UUID(job_id),
        collection["id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="S3 ingest job not found")

    return _row_to_response(dict(row))


@router.post("/{job_id}/resync")
async def resync_s3_job(
    collection_name: str,
    job_id: str,
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)
    row = await db.fetchrow(
        "SELECT * FROM s3_ingest_jobs WHERE id = $1 AND collection_id = $2",
        uuid.UUID(job_id),
        collection["id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="S3 ingest job not found")

    # Reset the job status and re-start it
    await db.execute(
        "UPDATE s3_ingest_jobs SET status = 'pending', total_found = 0, "
        "total_ingested = 0, total_skipped = 0, error_message = NULL, "
        "updated_at = now() WHERE id = $1",
        uuid.UUID(job_id),
    )

    from bigrag.services.s3_ingest import _start_job, cancel_job

    cancel_job(job_id)  # cancel if still running

    updated_row = await db.fetchrow(
        "SELECT * FROM s3_ingest_jobs WHERE id = $1", uuid.UUID(job_id)
    )
    _start_job(dict(updated_row))

    return {"status": "ok", "message": "S3 ingest job re-syncing"}


@router.delete("/{job_id}")
async def delete_s3_job(
    collection_name: str,
    job_id: str,
    _: dict = Depends(get_current_user),
):
    collection = await get_collection_or_404(collection_name)

    row = await db.fetchrow(
        "SELECT * FROM s3_ingest_jobs WHERE id = $1 AND collection_id = $2",
        uuid.UUID(job_id),
        collection["id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="S3 ingest job not found")

    from bigrag.services.s3_ingest import cancel_job

    cancel_job(job_id)
    await db.execute("DELETE FROM s3_ingest_jobs WHERE id = $1", uuid.UUID(job_id))

    return {"status": "ok", "message": "S3 ingest job deleted"}
