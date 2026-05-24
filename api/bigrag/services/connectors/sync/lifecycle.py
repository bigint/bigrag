from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.services.connectors.manifest import apply_counters
from bigrag.services.connectors.progress import update_sync_progress
from bigrag.services.connectors.realtime import notify_connector_sources
from bigrag.services.connectors.time import next_sync_at, utcnow
from bigrag.services.connectors.types import ConnectorSyncAdapter, ConnectorSyncCounters
from bigrag.services.webhook import enqueue_webhook_event


async def mark_sync_running(
    session: AsyncSession,
    *,
    adapter: ConnectorSyncAdapter,
    job,
    source,
    counters: ConnectorSyncCounters,
) -> None:
    now = utcnow()
    job.status = "running"
    job.started_at = now
    source.status = "syncing"
    source.last_error = None
    await update_sync_progress(
        session,
        job=job,
        source=source,
        counters=counters,
        phase="authenticating",
        message="Connecting to source",
    )
    await enqueue_webhook_event(
        "connector.sync.started",
        collection=source.collection_name,
        data={
            "provider": adapter.provider,
            "source_id": str(source.id),
            "job_id": str(job.id),
            "trigger": job.trigger,
            "collection": source.collection_name,
            "status": job.status,
        },
    )


async def mark_sync_deferred_by_queue(
    session: AsyncSession,
    *,
    adapter: ConnectorSyncAdapter,
    job,
    source,
    counters: ConnectorSyncCounters,
) -> None:
    completed = utcnow()
    job.status = "complete"
    job.error_message = None
    job.completed_at = completed
    apply_counters(job, counters)
    source.status = "idle"
    source.last_sync_at = completed
    source.next_sync_at = next_sync_at(source, from_time=completed)
    source.last_error = None
    await update_sync_progress(
        session,
        job=job,
        source=source,
        counters=counters,
        phase="complete",
        message="Ingestion queue full; remaining files will sync on the next run.",
    )
    notify_connector_sources(adapter.provider, source.collection_name)
