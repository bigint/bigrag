from __future__ import annotations

from typing import Any

from bigrag.db.models import ConnectorDocument, ConnectorSource, ConnectorSyncJob
from bigrag.services.connectors.realtime import notify_connector_sync_jobs
from bigrag.services.connectors.types import ConnectorSyncCounters, RemoteConnectorFile

SYNC_PROGRESS_FIXED_PERCENT = {
    "queued": 0,
    "authenticating": 5,
    "scanning": 12,
    "finalizing": 98,
    "complete": 100,
    "failed": 100,
}

SYNC_PROGRESS_RANGES = {
    "syncing": (15, 85),
    "removing": (85, 95),
}


def sync_progress_percent(phase: str, processed_items: int = 0, total_items: int = 0) -> int:
    if phase in SYNC_PROGRESS_FIXED_PERCENT:
        return SYNC_PROGRESS_FIXED_PERCENT[phase]
    start, end = SYNC_PROGRESS_RANGES.get(phase, (0, 0))
    if total_items <= 0:
        return start
    ratio = min(1.0, max(0.0, processed_items / total_items))
    return round(start + ((end - start) * ratio))


def sync_counter_details(counters: ConnectorSyncCounters) -> dict[str, int]:
    return {
        "created": counters.created,
        "updated": counters.updated,
        "skipped": counters.skipped,
        "deleted": counters.deleted,
        "failed": counters.failed,
    }


def sync_progress_details(
    *,
    phase: str,
    message: str,
    counters: ConnectorSyncCounters | None = None,
    current_item: RemoteConnectorFile | ConnectorDocument | None = None,
    processed_items: int = 0,
    total_items: int = 0,
) -> dict[str, Any]:
    current_item_id = getattr(current_item, "id", None) or getattr(current_item, "remote_id", None)
    current_item_name = getattr(current_item, "name", None) or getattr(
        current_item, "remote_name", None
    )
    counts = sync_counter_details(counters or ConnectorSyncCounters())
    return {
        "phase": phase,
        "message": message,
        "current_item_id": str(current_item_id) if current_item_id else None,
        "current_item_name": current_item_name,
        "progress_percent": sync_progress_percent(phase, processed_items, total_items),
        "processed_items": processed_items,
        "total_items": total_items,
        "counts": counts,
    }


async def update_sync_progress(
    session: Any,
    *,
    job: ConnectorSyncJob,
    source: ConnectorSource | None = None,
    counters: ConnectorSyncCounters,
    phase: str,
    message: str,
    current_item: RemoteConnectorFile | ConnectorDocument | None = None,
    processed_items: int = 0,
    total_items: int = 0,
) -> None:
    job.total_found = counters.found
    job.total_created = counters.created
    job.total_updated = counters.updated
    job.total_skipped = counters.skipped
    job.total_deleted = counters.deleted
    job.total_failed = counters.failed
    job.details = {
        **dict(job.details or {}),
        "errors": counters.errors,
        "progress": sync_progress_details(
            phase=phase,
            message=message,
            counters=counters,
            current_item=current_item,
            processed_items=processed_items,
            total_items=total_items,
        ),
    }
    await session.commit()
    if source is not None:
        notify_connector_sync_jobs(job.provider, source.collection_name, str(source.id))
