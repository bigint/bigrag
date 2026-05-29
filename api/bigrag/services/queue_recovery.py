from __future__ import annotations

import uuid

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import Document
from bigrag.logging import get_logger
from bigrag.services import queue_state
from bigrag.services.ingestion_job import IngestionJob

logger = get_logger("bigrag.queue")


async def recover_stuck_jobs(redis) -> int:
    from bigrag.services.jobs.actors import enqueue_ingestion_job

    jobs = await queue_state.recover_stuck_jobs(redis)
    if jobs:
        recovered_jobs = await mark_recovered_jobs_pending(jobs)
        for job in recovered_jobs:
            enqueue_ingestion_job(job)
        await redis.hincrby(queue_state.STATS_KEY, "queued", len(recovered_jobs))
        logger.info("queue requeued stuck jobs", recovered=len(recovered_jobs))
        return len(recovered_jobs)
    return 0


async def mark_recovered_jobs_pending(jobs: list[IngestionJob]) -> list[IngestionJob]:
    ids = [uuid.UUID(job.document_id) for job in jobs]
    async with session_factory()() as session:
        result = await session.scalars(
            sa.update(Document)
            .where(Document.id.in_(ids))
            .where(Document.status.in_(("pending", "processing")))
            .values(
                status="pending",
                error_message="Recovered stale processing lease; requeued.",
            )
            .returning(Document.id)
        )
        recovered_ids = {str(document_id) for document_id in result.all()}
        await session.commit()
    return [job for job in jobs if job.document_id in recovered_ids]
