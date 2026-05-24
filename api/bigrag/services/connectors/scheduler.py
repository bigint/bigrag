from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import ConnectorSource, ConnectorSyncJob
from bigrag.services.connectors.realtime import notify_connector_state
from bigrag.services.connectors.sources import create_sync_job
from bigrag.services.connectors.time import next_sync_at, utcnow

STALE_SYNC_AFTER_SECONDS = 1800


async def reap_stale_syncs(session, *, provider: str) -> int:
    cutoff = utcnow() - timedelta(seconds=STALE_SYNC_AFTER_SECONDS)
    stale_jobs = (
        await session.scalars(
            sa.select(ConnectorSyncJob)
            .where(ConnectorSyncJob.provider == provider)
            .where(ConnectorSyncJob.status.in_(("pending", "running")))
            .where(ConnectorSyncJob.updated_at < cutoff)
            .with_for_update(skip_locked=True)
        )
    ).all()
    if not stale_jobs:
        return 0
    now = utcnow()
    message = "Sync stopped responding and was reset"
    for job in stale_jobs:
        job.status = "failed"
        job.error_message = message
        job.completed_at = now
        if job.source_id is None:
            continue
        source = await session.get(ConnectorSource, job.source_id)
        if source is not None and source.status == "syncing":
            source.status = "error"
            source.last_error = message
            source.next_sync_at = next_sync_at(source, from_time=now)
    await session.commit()
    return len(stale_jobs)


async def run_due_syncs(
    *,
    provider: str,
    start_sync_job: Callable[[str], None],
    queued_message: str,
    limit: int = 10,
) -> int:
    from bigrag.services.maintenance import is_active

    if await is_active():
        return 0
    async with session_factory()() as session:
        await reap_stale_syncs(session, provider=provider)
    job_ids: list[str] = []
    notifications: list[tuple[str, str, str]] = []
    async with session_factory()() as session:
        rows = (
            await session.scalars(
                sa.select(ConnectorSource)
                .where(ConnectorSource.provider == provider)
                .where(ConnectorSource.schedule_enabled.is_(True))
                .where(ConnectorSource.next_sync_at.is_not(None))
                .where(ConnectorSource.next_sync_at <= utcnow())
                .where(ConnectorSource.status != "syncing")
                .order_by(ConnectorSource.next_sync_at.asc())
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        ).all()
        for source in rows:
            job = await create_sync_job(
                session,
                provider=provider,
                source=source,
                trigger="scheduled",
                user_id=None,
                queued_message=queued_message,
                commit=False,
            )
            await session.flush()
            notifications.append((provider, source.collection_name, str(source.id)))
            if job.status == "pending" and job.started_at is None:
                job_ids.append(str(job.id))
        await session.commit()
    for event in notifications:
        notify_connector_state(*event)
    for job_id in job_ids:
        start_sync_job(job_id)
    return len(job_ids)
