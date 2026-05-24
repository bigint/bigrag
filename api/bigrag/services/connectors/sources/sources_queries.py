from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import sqlalchemy as sa

from bigrag.db.models import ConnectorSource, ConnectorSyncJob
from bigrag.services.connectors.sources.sources_public import source_public, sync_job_public


async def list_sources(
    session: Any,
    *,
    provider: str,
    shape_config: Callable[[ConnectorSource], dict[str, Any]],
    collection_name: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    stmt = (
        sa.select(ConnectorSource)
        .where(ConnectorSource.provider == provider)
        .order_by(ConnectorSource.created_at.desc())
    )
    if collection_name:
        stmt = stmt.where(ConnectorSource.collection_name == collection_name)
    rows = (await session.scalars(stmt)).all()
    return [source_public(provider, row, shape_config=shape_config) for row in rows], len(rows)


async def source_by_id(
    session: Any,
    *,
    provider: str,
    source_id: str,
    not_found_message: str,
) -> ConnectorSource:
    source = await session.scalar(
        sa.select(ConnectorSource)
        .where(ConnectorSource.id == uuid.UUID(source_id))
        .where(ConnectorSource.provider == provider)
    )
    if source is None:
        raise ValueError(not_found_message)
    return source


async def list_sync_jobs(
    session: Any,
    *,
    provider: str,
    collection_name: str | None,
    source_id: str | None,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    stmt = (
        sa.select(ConnectorSyncJob)
        .join(ConnectorSource, ConnectorSource.id == ConnectorSyncJob.source_id)
        .where(ConnectorSyncJob.provider == provider)
        .order_by(ConnectorSyncJob.created_at.desc())
        .limit(limit)
    )
    count_stmt = (
        sa.select(sa.func.count())
        .select_from(ConnectorSyncJob)
        .join(ConnectorSource, ConnectorSource.id == ConnectorSyncJob.source_id)
        .where(ConnectorSyncJob.provider == provider)
    )
    if source_id:
        sid = uuid.UUID(source_id)
        stmt = stmt.where(ConnectorSyncJob.source_id == sid)
        count_stmt = count_stmt.where(ConnectorSyncJob.source_id == sid)
    if collection_name:
        stmt = stmt.where(ConnectorSource.collection_name == collection_name)
        count_stmt = count_stmt.where(ConnectorSource.collection_name == collection_name)
    rows = (await session.scalars(stmt)).all()
    total = await session.scalar(count_stmt)
    return [sync_job_public(provider, job) for job in rows], total or 0
