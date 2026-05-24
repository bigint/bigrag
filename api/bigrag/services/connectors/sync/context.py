from __future__ import annotations

import uuid
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Collection, ConnectorSource, ConnectorSyncJob
from bigrag.services.connectors.types import ConnectorSyncAdapter


@dataclass(frozen=True)
class ConnectorSyncContext:
    job: ConnectorSyncJob
    source: ConnectorSource
    collection: Collection | None


async def lock_pending_sync_context(
    session: AsyncSession,
    *,
    job_id: str,
    adapter: ConnectorSyncAdapter,
) -> ConnectorSyncContext | None:
    job = await session.scalar(
        sa.select(ConnectorSyncJob)
        .where(ConnectorSyncJob.id == uuid.UUID(job_id))
        .with_for_update()
    )
    if job is None or job.source_id is None:
        return None
    if job.status != "pending":
        return None
    source = await session.get(ConnectorSource, job.source_id)
    if source is None or source.provider != adapter.provider:
        return None
    collection = await session.get(Collection, source.collection_id)
    return ConnectorSyncContext(job=job, source=source, collection=collection)
