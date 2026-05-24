from __future__ import annotations

import asyncio
import uuid

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import Collection, ConnectorSource, ConnectorSyncJob
from bigrag.logging import get_logger
from bigrag.services.connectors.manifest import apply_counters
from bigrag.services.connectors.progress import update_sync_progress
from bigrag.services.connectors.realtime import notify_connector_sources
from bigrag.services.connectors.status import fail_sync
from bigrag.services.connectors.sync.finalize import finalize_sync
from bigrag.services.connectors.sync.prune_stale import prune_stale
from bigrag.services.connectors.sync.scan_pages import scan_pages
from bigrag.services.connectors.time import next_sync_at, utcnow
from bigrag.services.connectors.types import ConnectorSyncAdapter, ConnectorSyncCounters
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.queue import QueueFullError
from bigrag.services.webhook import enqueue_webhook_event

logger = get_logger("bigrag.connectors")


async def sync_connector_job(job_id: str, adapter: ConnectorSyncAdapter) -> None:
    from bigrag.services.maintenance import ensure_writes_allowed

    counters = ConnectorSyncCounters()
    now = utcnow()
    async with session_factory()() as session:
        job = await session.scalar(
            sa.select(ConnectorSyncJob)
            .where(ConnectorSyncJob.id == uuid.UUID(job_id))
            .with_for_update()
        )
        if job is None or job.source_id is None:
            return
        if job.status != "pending":
            return
        source = await session.get(ConnectorSource, job.source_id)
        if source is None or source.provider != adapter.provider:
            return
        collection = await session.get(Collection, source.collection_id)

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
            message="Connecting to S3",
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

        if collection is None:
            await fail_sync(
                session,
                job=job,
                source=source,
                message="Collection not found",
                counters=counters,
            )
            return

        try:
            await ensure_writes_allowed()
            await update_sync_progress(
                session,
                job=job,
                source=source,
                counters=counters,
                phase="scanning",
                message="Scanning remote objects",
            )

            from bigrag.services.runtime_settings import get_value

            download_concurrency = await get_value("connector_download_concurrency")
            job_uuid = job.id
            await scan_pages(
                session,
                adapter=adapter,
                job=job,
                source=source,
                collection=collection,
                counters=counters,
                download_concurrency=download_concurrency,
                job_uuid=job_uuid,
            )
            missing_count = await prune_stale(
                session,
                job=job,
                source=source,
                counters=counters,
                job_uuid=job_uuid,
            )
            await finalize_sync(
                session,
                adapter=adapter,
                job=job,
                source=source,
                counters=counters,
                missing_count=missing_count,
                job_id=job_id,
            )
        except asyncio.CancelledError:
            await fail_sync(
                session,
                job=job,
                source=source,
                message="Sync cancelled",
                counters=counters,
            )
            raise
        except QueueFullError:
            logger.info(
                "connector: sync deferred, ingestion queue full",
                provider=adapter.provider,
                job_id=job_id,
            )
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
        except BaseException as exc:
            logger.exception(
                "connector: sync job failed",
                provider=adapter.provider,
                job_id=job_id,
            )
            await fail_sync(
                session,
                job=job,
                source=source,
                message=sanitize_message_text(str(exc)) or "Sync failed",
                counters=counters,
            )
