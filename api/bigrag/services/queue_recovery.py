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
        await mark_recovered_jobs_pending(jobs)
        for job in jobs:
            enqueue_ingestion_job(job)
        await redis.hincrby(queue_state.STATS_KEY, "queued", len(jobs))
        logger.info("queue requeued stuck jobs", recovered=len(jobs))
    return len(jobs)


async def mark_recovered_jobs_pending(jobs: list[IngestionJob]) -> None:
    ids = [uuid.UUID(job.document_id) for job in jobs]
    async with session_factory()() as session:
        await session.execute(
            sa.update(Document)
            .where(Document.id.in_(ids))
            .values(
                status="pending",
                error_message="Recovered stale processing lease; requeued.",
            )
        )
        await session.commit()
