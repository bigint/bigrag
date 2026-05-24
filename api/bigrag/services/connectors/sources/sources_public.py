from __future__ import annotations

from collections.abc import Callable
from typing import Any

from bigrag.db.models import ConnectorSource, ConnectorSyncJob


def source_public(
    provider: str,
    source: ConnectorSource,
    *,
    shape_config: Callable[[ConnectorSource], dict[str, Any]],
) -> dict[str, Any]:
    metadata = dict(source.meta or {})
    return {
        "id": str(source.id),
        "provider": provider,
        "collection_name": source.collection_name,
        **shape_config(source),
        "root_id": source.root_id,
        "root_name": source.root_name,
        "source_type": source.source_type,
        "status": source.status,
        "schedule_enabled": source.schedule_enabled,
        "sync_interval_hours": source.sync_interval_hours,
        "last_sync_at": source.last_sync_at,
        "next_sync_at": source.next_sync_at,
        "last_error": source.last_error,
        "metadata": metadata.get("user_metadata") or {},
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def sync_job_public(provider: str, job: ConnectorSyncJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "provider": provider,
        "source_id": str(job.source_id) if job.source_id else None,
        "trigger": job.trigger,
        "status": job.status,
        "total_found": job.total_found,
        "total_created": job.total_created,
        "total_updated": job.total_updated,
        "total_skipped": job.total_skipped,
        "total_deleted": job.total_deleted,
        "total_failed": job.total_failed,
        "error_message": job.error_message,
        "details": job.details or {},
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
