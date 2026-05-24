from __future__ import annotations

import asyncio

from bigrag.db.engine import session_factory
from bigrag.logging import get_logger
from bigrag.services.connectors.progress import update_sync_progress
from bigrag.services.connectors.status import fail_sync
from bigrag.services.connectors.sync.context import lock_pending_sync_context
from bigrag.services.connectors.sync.finalize import finalize_sync
from bigrag.services.connectors.sync.lifecycle import (
    mark_sync_deferred_by_queue,
    mark_sync_running,
)
from bigrag.services.connectors.sync.prune_stale import prune_stale
from bigrag.services.connectors.sync.scan_pages import scan_pages
from bigrag.services.connectors.types import ConnectorSyncAdapter, ConnectorSyncCounters
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.queue import QueueFullError

logger = get_logger("bigrag.connectors")


async def sync_connector_job(job_id: str, adapter: ConnectorSyncAdapter) -> None:
    from bigrag.services.maintenance import ensure_writes_allowed

    counters = ConnectorSyncCounters()
    async with session_factory()() as session:
        context = await lock_pending_sync_context(session, job_id=job_id, adapter=adapter)
        if context is None:
            return
        job = context.job
        source = context.source
        collection = context.collection

        await mark_sync_running(
            session,
            adapter=adapter,
            job=job,
            source=source,
            counters=counters,
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
            await mark_sync_deferred_by_queue(
                session,
                adapter=adapter,
                job=job,
                source=source,
                counters=counters,
            )
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
