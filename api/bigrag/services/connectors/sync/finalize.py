from __future__ import annotations

from bigrag.db.models import ConnectorSource, ConnectorSyncJob
from bigrag.logging import get_logger
from bigrag.services import collection_cache
from bigrag.services.connectors.manifest import apply_counters
from bigrag.services.connectors.progress import sync_counter_details, update_sync_progress
from bigrag.services.connectors.realtime import notify_connector_sources
from bigrag.services.connectors.time import next_sync_at, utcnow
from bigrag.services.connectors.types import ConnectorSyncAdapter, ConnectorSyncCounters
from bigrag.services.documents import recount_collection_documents
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.webhook import enqueue_webhook_event

logger = get_logger("bigrag.connectors")


async def finalize_sync(
    session,
    *,
    adapter: ConnectorSyncAdapter,
    job: ConnectorSyncJob,
    source: ConnectorSource,
    counters: ConnectorSyncCounters,
    missing_count: int,
    job_id: str,
) -> None:
    await update_sync_progress(
        session,
        job=job,
        source=source,
        counters=counters,
        phase="finalizing",
        message="Queueing synced documents for ingestion",
    )

    completed = utcnow()
    job.status = "complete" if counters.failed == 0 else "failed"
    job.error_message = None if counters.failed == 0 else adapter.partial_failure_message
    job.completed_at = completed
    apply_counters(job, counters)
    source.status = "idle" if counters.failed == 0 else "error"
    source.last_sync_at = completed
    source.next_sync_at = next_sync_at(source, from_time=completed)
    source.last_error = job.error_message
    await recount_collection_documents(session, source.collection_id)
    await update_sync_progress(
        session,
        job=job,
        source=source,
        counters=counters,
        phase="complete" if counters.failed == 0 else "failed",
        message=(
            "S3 sync complete. Documents queued for ingestion."
            if counters.failed == 0
            else adapter.partial_failure_message
        ),
        processed_items=counters.found + counters.deleted,
        total_items=counters.found + missing_count,
    )
    notify_connector_sources(adapter.provider, source.collection_name)
    await collection_cache.invalidate(source.collection_name)
    await invalidate_collection_query_cache(source.collection_name)
    webhook_event = (
        "connector.sync.completed" if job.status == "complete" else "connector.sync.failed"
    )
    await enqueue_webhook_event(
        webhook_event,
        collection=source.collection_name,
        data={
            "provider": adapter.provider,
            "source_id": str(source.id),
            "job_id": str(job.id),
            "trigger": job.trigger,
            "collection": source.collection_name,
            "status": job.status,
            "error_message": job.error_message,
            "counts": {
                "found": counters.found,
                **sync_counter_details(counters),
            },
        },
    )
    logger.info(
        "connector: sync complete",
        provider=adapter.provider,
        job_id=job_id,
        source_id=str(source.id),
        found=counters.found,
        created=counters.created,
        updated=counters.updated,
        skipped=counters.skipped,
        deleted=counters.deleted,
        failed=counters.failed,
    )
