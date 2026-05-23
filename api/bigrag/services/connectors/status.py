from __future__ import annotations

from typing import Any

from bigrag.db.models import ConnectorSource, ConnectorSyncJob
from bigrag.services.connectors.manifest import apply_counters
from bigrag.services.connectors.progress import sync_counter_details, update_sync_progress
from bigrag.services.connectors.time import next_sync_at, utcnow
from bigrag.services.connectors.types import ConnectorSyncCounters
from bigrag.services.webhook import enqueue_webhook_event


async def fail_sync(
    session: Any,
    *,
    job: ConnectorSyncJob,
    source: ConnectorSource,
    message: str,
    counters: ConnectorSyncCounters | None = None,
) -> None:
    counters = counters or ConnectorSyncCounters()
    completed = utcnow()
    job.status = "failed"
    job.error_message = message
    job.completed_at = completed
    apply_counters(job, counters)
    source.status = "error"
    source.last_sync_at = completed
    source.next_sync_at = next_sync_at(source, from_time=completed)
    source.last_error = message
    await update_sync_progress(
        session,
        job=job,
        counters=counters,
        phase="failed",
        message=message,
    )
    data = {
        "provider": job.provider,
        "source_id": str(source.id),
        "job_id": str(job.id),
        "trigger": job.trigger,
        "collection": source.collection_name,
        "status": job.status,
        "error_message": message,
        "counts": {
            "found": counters.found,
            **sync_counter_details(counters),
        },
    }
    await enqueue_webhook_event(
        "connector.sync.failed",
        collection=source.collection_name,
        data=data,
    )
