from __future__ import annotations

import uuid

import sqlalchemy as sa

from bigrag.db.models import Collection, ConnectorDocument, ConnectorSource, ConnectorSyncJob
from bigrag.services.connectors.batches import sync_page
from bigrag.services.connectors.progress import update_sync_progress
from bigrag.services.connectors.types import ConnectorSyncAdapter, ConnectorSyncCounters


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


async def scan_pages(
    session,
    *,
    adapter: ConnectorSyncAdapter,
    job: ConnectorSyncJob,
    source: ConnectorSource,
    collection: Collection,
    counters: ConnectorSyncCounters,
    download_concurrency: int,
    job_uuid: uuid.UUID,
) -> None:
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
