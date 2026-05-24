from __future__ import annotations

import uuid

import sqlalchemy as sa

from bigrag.db.models import ConnectorDocument, ConnectorSource, ConnectorSyncJob
from bigrag.services.connectors.documents import delete_synced_document
from bigrag.services.connectors.progress import update_sync_progress
from bigrag.services.connectors.types import ConnectorDeleteSafetyError, ConnectorSyncCounters

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


async def prune_stale(
    session,
    *,
    job: ConnectorSyncJob,
    source: ConnectorSource,
    counters: ConnectorSyncCounters,
    job_uuid: uuid.UUID,
) -> int:
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
    return missing_count
