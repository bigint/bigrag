from __future__ import annotations

import asyncio
import uuid

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import (
    Collection,
    ConnectorDocument,
    ConnectorSource,
    ConnectorSyncJob,
)
from bigrag.logging import get_logger
from bigrag.services import collection_cache
from bigrag.services.connectors.batches import sync_page
from bigrag.services.connectors.documents import (
    delete_synced_document,
    sync_downloaded_file,
)
from bigrag.services.connectors.manifest import (
    apply_counters,
    collection_dict_for_sync,
    manifest_for_download,
    manifest_remote_unchanged,
    manifest_unchanged,
    remote_signature,
    update_manifest,
    update_manifest_remote,
)
from bigrag.services.connectors.progress import sync_counter_details, update_sync_progress
from bigrag.services.connectors.realtime import notify_connector_sources
from bigrag.services.connectors.status import fail_sync
from bigrag.services.connectors.time import next_sync_at, utcnow
from bigrag.services.connectors.types import (
    ConnectorDeleteSafetyError,
    ConnectorSyncAdapter,
    ConnectorSyncCounters,
)
from bigrag.services.documents import recount_collection_documents
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.queue import QueueFullError
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.webhook import enqueue_webhook_event

logger = get_logger("bigrag.connectors")

CONNECTOR_DELETE_SAFETY_MIN_TRACKED = 10
CONNECTOR_DELETE_BATCH_SIZE = 200


async def _guard_deletion_safety(missing: int, tracked: int) -> None:
    from bigrag.services.runtime_settings import get_value

    if missing == 0 or tracked < CONNECTOR_DELETE_SAFETY_MIN_TRACKED:
        return
    max_percent = await get_value("connector_max_delete_percent")
    if missing * 100 > tracked * max_percent:
        raise ConnectorDeleteSafetyError(
            f"Refusing to remove {missing} of {tracked} tracked files "
            f"(over {max_percent}% safety limit); verify the source and re-sync."
        )


def _processed_count(counters: ConnectorSyncCounters) -> int:
    return counters.created + counters.updated + counters.skipped + counters.failed


async def _load_page_manifests(
    session, source_id: uuid.UUID, remote_ids: list[str]
) -> dict[str, ConnectorDocument]:
    if not remote_ids:
        return {}
    rows = (
        await session.scalars(
            sa.select(ConnectorDocument).where(
                ConnectorDocument.source_id == source_id,
                ConnectorDocument.remote_id.in_(remote_ids),
            )
        )
    ).all()
    return {manifest.remote_id: manifest for manifest in rows}


async def _count_manifests(session, source_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            sa.select(sa.func.count())
            .select_from(ConnectorDocument)
            .where(ConnectorDocument.source_id == source_id)
        )
        or 0
    )


async def _count_unseen_manifests(session, source_id: uuid.UUID, job_uuid: uuid.UUID) -> int:
    return (
        await session.scalar(
            sa.select(sa.func.count())
            .select_from(ConnectorDocument)
            .where(
                ConnectorDocument.source_id == source_id,
                ConnectorDocument.last_seen_job_id.is_distinct_from(job_uuid),
            )
        )
        or 0
    )


__all__ = [
    "apply_counters",
    "collection_dict_for_sync",
    "delete_synced_document",
    "fail_sync",
    "manifest_for_download",
    "manifest_remote_unchanged",
    "manifest_unchanged",
    "remote_signature",
    "sync_connector_job",
    "sync_downloaded_file",
    "update_manifest",
    "update_manifest_remote",
]


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
            async for page in adapter.iter_files(session, source=source):
                counters.found += len(page)
                page_ids = [remote.id for remote in page]
                page_manifests = await _load_page_manifests(session, source.id, page_ids)
                await sync_page(
                    session,
                    adapter=adapter,
                    source=source,
                    collection=collection,
                    remotes=page,
                    manifests=page_manifests,
                    counters=counters,
                    download_concurrency=download_concurrency,
                )
                await session.execute(
                    sa.update(ConnectorDocument)
                    .where(
                        ConnectorDocument.source_id == source.id,
                        ConnectorDocument.remote_id.in_(page_ids),
                    )
                    .values(last_seen_job_id=job_uuid)
                )
                await session.commit()
                processed = _processed_count(counters)
                await update_sync_progress(
                    session,
                    job=job,
                    source=source,
                    counters=counters,
                    phase="syncing",
                    message=f"Synced {processed} of {counters.found} remote files",
                    processed_items=processed,
                    total_items=counters.found,
                )

            tracked = await _count_manifests(session, source.id)
            missing_count = await _count_unseen_manifests(session, source.id, job_uuid)
            await _guard_deletion_safety(missing_count, tracked)
            await update_sync_progress(
                session,
                job=job,
                source=source,
                counters=counters,
                phase="removing",
                message="Checking for removed remote objects",
                processed_items=0,
                total_items=missing_count,
            )
            removed = 0
            while True:
                stale = (
                    await session.scalars(
                        sa.select(ConnectorDocument)
                        .where(
                            ConnectorDocument.source_id == source.id,
                            ConnectorDocument.last_seen_job_id.is_distinct_from(job_uuid),
                        )
                        .limit(CONNECTOR_DELETE_BATCH_SIZE)
                    )
                ).all()
                if not stale:
                    break
                for manifest in stale:
                    await delete_synced_document(
                        session,
                        source=source,
                        manifest=manifest,
                        counters=counters,
                    )
                await session.commit()
                removed += len(stale)
                await update_sync_progress(
                    session,
                    job=job,
                    source=source,
                    counters=counters,
                    phase="removing",
                    message=f"Removed {removed} of {missing_count} missing remote files",
                    processed_items=removed,
                    total_items=missing_count,
                )

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
