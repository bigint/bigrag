from __future__ import annotations

from typing import Any

from bigrag.db.models import ConnectorSource, ConnectorSyncJob
from bigrag.services.connectors.manifest import apply_counters
from bigrag.services.connectors.progress import update_sync_progress
from bigrag.services.connectors.time import next_sync_at, utcnow
from bigrag.services.connectors.types import ConnectorSyncCounters


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
    if source.status != "needs_reauth":
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
