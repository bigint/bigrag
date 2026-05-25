from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import sqlalchemy as sa

from bigrag.db.models import (
    Collection,
    ConnectorDocument,
    ConnectorSource,
    ConnectorSyncJob,
)
from bigrag.services import collection_cache
from bigrag.services.connectors.progress import sync_progress_details
from bigrag.services.connectors.sources.sources_credentials import upsert_source_credential
from bigrag.services.connectors.sources.sources_queries import source_by_id
from bigrag.services.connectors.time import next_sync_at, utcnow
from bigrag.services.retrieval import invalidate_collection_query_cache


async def create_sync_job(
    session: Any,
    *,
    provider: str,
    source: ConnectorSource,
    trigger: str,
    user_id: str | None,
    queued_message: str,
    commit: bool = True,
) -> ConnectorSyncJob:
    from bigrag.services.maintenance import MaintenanceActiveError, ensure_writes_allowed

    try:
        await ensure_writes_allowed()
    except MaintenanceActiveError as exc:
        raise ValueError(str(exc)) from exc
    locked_source = await session.scalar(
        sa.select(ConnectorSource)
        .where(ConnectorSource.id == source.id)
        .where(ConnectorSource.status != "syncing")
        .with_for_update()
    )
    existing = await session.scalar(
        sa.select(ConnectorSyncJob)
        .where(ConnectorSyncJob.source_id == source.id)
        .where(ConnectorSyncJob.status.in_(("pending", "running")))
        .order_by(ConnectorSyncJob.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        return existing
    if locked_source is None:
        raise ValueError("Source is already syncing")

    source.status = "syncing"
    source.last_error = None
    job = ConnectorSyncJob(
        provider=provider,
        source_id=source.id,
        trigger=trigger,
        status="pending",
        started_by=uuid.UUID(user_id) if user_id else None,
        details={
            "errors": [],
            "progress": sync_progress_details(
                phase="queued",
                message=queued_message,
            ),
        },
    )
    session.add(job)
    if commit:
        await session.commit()
        await session.refresh(job)
    return job


async def create_source(
    session: Any,
    *,
    provider: str,
    collection_name: str,
    root_id: str,
    root_name: str,
    metadata: dict,
    user_id: str,
    schedule_enabled: bool,
    sync_interval_hours: int,
    start_sync_job: Callable[[str], None],
    credential_values: dict[str, Any],
    queued_message: str,
) -> tuple[ConnectorSource, ConnectorSyncJob]:
    collection = await session.scalar(
        sa.select(Collection).where(Collection.name == collection_name)
    )
    if collection is None:
        raise ValueError("Collection not found")

    collection_id = collection.id
    collection_name_value = collection.name
    metadata_dict = dict(metadata or {})
    source = ConnectorSource(
        provider=provider,
        collection_id=collection_id,
        collection_name=collection_name_value,
        tenant_id=_tenant_id(collection, metadata_dict),
        root_id=root_id,
        root_name=root_name,
        source_type="prefix",
        schedule_enabled=schedule_enabled,
        sync_interval_hours=sync_interval_hours,
        status="idle",
        next_sync_at=utcnow() + timedelta(hours=sync_interval_hours) if schedule_enabled else None,
        meta=metadata_dict,
    )
    session.add(source)
    try:
        await session.flush()
    except sa.exc.IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            sa.select(ConnectorSource)
            .where(ConnectorSource.provider == provider)
            .where(ConnectorSource.collection_id == collection_id)
            .where(ConnectorSource.root_id == root_id)
        )
        if existing is None:
            raise
        await upsert_source_credential(session, source=existing, **credential_values)
        existing.meta = metadata_dict
        existing.schedule_enabled = schedule_enabled
        existing.sync_interval_hours = sync_interval_hours
        existing.next_sync_at = next_sync_at(existing)
        job = await create_sync_job(
            session,
            provider=provider,
            source=existing,
            trigger="initial",
            user_id=user_id,
            queued_message=queued_message,
            commit=False,
        )
        await session.commit()
        await session.refresh(existing)
        if job.status == "pending" and job.started_at is None:
            start_sync_job(str(job.id))
        return existing, job

    await upsert_source_credential(session, source=source, **credential_values)
    job = await create_sync_job(
        session,
        provider=provider,
        source=source,
        trigger="initial",
        user_id=user_id,
        queued_message=queued_message,
        commit=False,
    )
    await session.commit()
    await session.refresh(source)
    await session.refresh(job)
    if job.status == "pending" and job.started_at is None:
        start_sync_job(str(job.id))
    return source, job


async def trigger_sync(
    session: Any,
    *,
    provider: str,
    user_id: str,
    source_id: str,
    not_found_message: str,
    start_sync_job: Callable[[str], None],
    queued_message: str,
    trigger: str = "manual",
) -> ConnectorSyncJob:
    source = await source_by_id(
        session,
        provider=provider,
        source_id=source_id,
        not_found_message=not_found_message,
    )
    job = await create_sync_job(
        session,
        provider=provider,
        source=source,
        trigger=trigger,
        user_id=user_id,
        queued_message=queued_message,
    )
    if job.status == "pending" and job.started_at is None:
        start_sync_job(str(job.id))
    return job


async def update_source(
    session: Any,
    *,
    provider: str,
    source_id: str,
    not_found_message: str,
    schedule_enabled: bool | None,
    sync_interval_hours: int | None,
    root_id: str | None = None,
    root_name: str | None = None,
    metadata: dict | None = None,
    credential_values: dict[str, Any] | None = None,
) -> ConnectorSource:
    source = await source_by_id(
        session,
        provider=provider,
        source_id=source_id,
        not_found_message=not_found_message,
    )
    if root_id is not None:
        source.root_id = root_id
    if root_name is not None:
        source.root_name = root_name
    if metadata is not None:
        source.meta = metadata
    if schedule_enabled is not None:
        source.schedule_enabled = schedule_enabled
    if sync_interval_hours is not None:
        source.sync_interval_hours = sync_interval_hours
    if credential_values is not None:
        await upsert_source_credential(session, source=source, **credential_values)
    source.next_sync_at = next_sync_at(source)
    await session.commit()
    await session.refresh(source)
    return source


async def delete_source(
    session: Any,
    *,
    provider: str,
    source_id: str,
    not_found_message: str,
) -> None:
    source = await source_by_id(
        session,
        provider=provider,
        source_id=source_id,
        not_found_message=not_found_message,
    )
    collection_name = source.collection_name
    manifests = (
        await session.scalars(
            sa.select(ConnectorDocument).where(ConnectorDocument.source_id == source.id)
        )
    ).all()
    if manifests:
        from bigrag.services.connectors.sync import delete_synced_document
        from bigrag.services.connectors.types import ConnectorSyncCounters
        from bigrag.services.documents import recount_collection_documents

        counters = ConnectorSyncCounters()
        for manifest in manifests:
            await delete_synced_document(
                session,
                source=source,
                manifest=manifest,
                counters=counters,
            )
        await recount_collection_documents(session, source.collection_id)
        await invalidate_collection_query_cache(source.collection_name)
    await session.delete(source)
    await session.commit()
    await collection_cache.invalidate(collection_name)


def _tenant_id(collection: Collection, metadata: dict[str, Any]) -> str | None:
    if collection.tenant_field:
        raw_tenant = metadata.get(collection.tenant_field)
        if isinstance(raw_tenant, str) and raw_tenant:
            return raw_tenant
    return None
