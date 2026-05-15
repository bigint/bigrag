from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import sqlalchemy as sa

from bigrag.db.models import (
    Collection,
    ConnectorAccount,
    ConnectorDocument,
    ConnectorSource,
    ConnectorSyncJob,
)
from bigrag.services import collection_cache
from bigrag.services.connectors.progress import sync_progress_details
from bigrag.services.connectors.time import next_sync_at, utcnow
from bigrag.services.retrieval import invalidate_collection_query_cache


def source_public(provider: str, row: tuple[ConnectorSource, ConnectorAccount]) -> dict[str, Any]:
    source, account = row
    return {
        "id": str(source.id),
        "provider": provider,
        "collection_name": source.collection_name,
        "root_id": source.root_id,
        "root_name": source.root_name,
        "root_mime_type": source.root_mime_type,
        "source_type": source.source_type,
        "status": source.status,
        "schedule_enabled": source.schedule_enabled,
        "sync_interval_hours": source.sync_interval_hours,
        "last_sync_at": source.last_sync_at,
        "next_sync_at": source.next_sync_at,
        "last_error": source.last_error,
        "account_email": account.account_email,
        "metadata": source.meta or {},
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


async def list_sources(
    session: Any,
    *,
    provider: str,
    user_id: str,
    collection_name: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    stmt = (
        sa.select(ConnectorSource, ConnectorAccount)
        .join(ConnectorAccount, ConnectorAccount.id == ConnectorSource.account_id)
        .where(ConnectorAccount.user_id == uuid.UUID(user_id))
        .where(ConnectorSource.provider == provider)
        .order_by(ConnectorSource.created_at.desc())
    )
    if collection_name:
        stmt = stmt.where(ConnectorSource.collection_name == collection_name)
    rows = (await session.execute(stmt)).all()
    return [source_public(provider, row) for row in rows], len(rows)


async def create_sync_job(
    session: Any,
    *,
    provider: str,
    source: ConnectorSource,
    trigger: str,
    user_id: str | None,
    commit: bool = True,
) -> ConnectorSyncJob:
    from bigrag.services.maintenance import MaintenanceActiveError, ensure_writes_allowed

    try:
        await ensure_writes_allowed()
    except MaintenanceActiveError as exc:
        raise ValueError(str(exc)) from exc
    await session.execute(
        sa.select(ConnectorSource.id).where(ConnectorSource.id == source.id).with_for_update()
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
                message="Google Drive sync queued",
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
    account: ConnectorAccount,
    collection_name: str,
    root_id: str,
    root_name: str,
    root_mime_type: str,
    source_type: str | None,
    metadata: dict,
    user_id: str,
    infer_source_type: Callable[[str], str],
    start_sync_job: Callable[[str], None],
) -> tuple[ConnectorSource, ConnectorSyncJob]:
    collection = await session.scalar(
        sa.select(Collection).where(Collection.name == collection_name)
    )
    if collection is None:
        raise ValueError("Collection not found")

    source = ConnectorSource(
        provider=provider,
        account_id=account.id,
        collection_id=collection.id,
        collection_name=collection.name,
        root_id=root_id,
        root_name=root_name,
        root_mime_type=root_mime_type or "",
        source_type=source_type or infer_source_type(root_mime_type),
        schedule_enabled=True,
        sync_interval_hours=24,
        status="syncing",
        next_sync_at=utcnow() + timedelta(hours=24),
        meta=dict(metadata or {}),
    )
    session.add(source)
    try:
        await session.flush()
    except sa.exc.IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            sa.select(ConnectorSource)
            .where(ConnectorSource.account_id == account.id)
            .where(ConnectorSource.collection_id == collection.id)
            .where(ConnectorSource.root_id == root_id)
        )
        if existing is None:
            raise
        job = await create_sync_job(
            session,
            provider=provider,
            source=existing,
            trigger="initial",
            user_id=user_id,
            commit=False,
        )
        await session.commit()
        if job.status == "pending" and job.started_at is None:
            start_sync_job(str(job.id))
        return existing, job

    job = await create_sync_job(
        session,
        provider=provider,
        source=source,
        trigger="initial",
        user_id=user_id,
        commit=False,
    )
    await session.commit()
    await session.refresh(source)
    await session.refresh(job)
    if job.status == "pending" and job.started_at is None:
        start_sync_job(str(job.id))
    return source, job


async def source_for_user(
    session: Any,
    *,
    provider: str,
    source_id: str,
    user_id: str,
    not_found_message: str,
) -> ConnectorSource:
    row = (
        await session.execute(
            sa.select(ConnectorSource)
            .join(ConnectorAccount, ConnectorAccount.id == ConnectorSource.account_id)
            .where(ConnectorSource.id == uuid.UUID(source_id))
            .where(ConnectorSource.provider == provider)
            .where(ConnectorAccount.user_id == uuid.UUID(user_id))
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError(not_found_message)
    return row


async def trigger_sync(
    session: Any,
    *,
    provider: str,
    user_id: str,
    source_id: str,
    not_found_message: str,
    start_sync_job: Callable[[str], None],
    trigger: str = "manual",
) -> ConnectorSyncJob:
    source = await source_for_user(
        session,
        provider=provider,
        source_id=source_id,
        user_id=user_id,
        not_found_message=not_found_message,
    )
    job = await create_sync_job(
        session,
        provider=provider,
        source=source,
        trigger=trigger,
        user_id=user_id,
    )
    if job.status == "pending" and job.started_at is None:
        start_sync_job(str(job.id))
    return job


async def update_source(
    session: Any,
    *,
    provider: str,
    user_id: str,
    source_id: str,
    not_found_message: str,
    schedule_enabled: bool | None,
    sync_interval_hours: int | None,
) -> ConnectorSource:
    source = await source_for_user(
        session,
        provider=provider,
        source_id=source_id,
        user_id=user_id,
        not_found_message=not_found_message,
    )
    if schedule_enabled is not None:
        source.schedule_enabled = schedule_enabled
    if sync_interval_hours is not None:
        source.sync_interval_hours = sync_interval_hours
    source.next_sync_at = next_sync_at(source)
    await session.commit()
    await session.refresh(source)
    return source


async def delete_source(
    session: Any,
    *,
    provider: str,
    user_id: str,
    source_id: str,
    not_found_message: str,
) -> None:
    source = await source_for_user(
        session,
        provider=provider,
        source_id=source_id,
        user_id=user_id,
        not_found_message=not_found_message,
    )
    manifests = (
        await session.scalars(
            sa.select(ConnectorDocument).where(ConnectorDocument.source_id == source.id)
        )
    ).all()
    if manifests:
        from bigrag.routers._documents import recount_collection_documents
        from bigrag.services.connectors.sync import delete_synced_document
        from bigrag.services.connectors.types import ConnectorSyncCounters

        counters = ConnectorSyncCounters()
        collection = await session.get(Collection, source.collection_id)
        for manifest in manifests:
            await delete_synced_document(
                session,
                collection=collection,
                source=source,
                manifest=manifest,
                counters=counters,
            )
        await recount_collection_documents(session, source.collection_id)
        await invalidate_collection_query_cache(source.collection_name)
    await session.delete(source)
    await session.commit()
    await collection_cache.invalidate(source.collection_name)


async def list_sync_jobs(
    session: Any,
    *,
    provider: str,
    user_id: str,
    collection_name: str | None,
    source_id: str | None,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    stmt = (
        sa.select(ConnectorSyncJob)
        .join(ConnectorSource, ConnectorSource.id == ConnectorSyncJob.source_id)
        .join(ConnectorAccount, ConnectorAccount.id == ConnectorSource.account_id)
        .where(ConnectorAccount.user_id == uuid.UUID(user_id))
        .where(ConnectorSyncJob.provider == provider)
        .order_by(ConnectorSyncJob.created_at.desc())
        .limit(limit)
    )
    count_stmt = (
        sa.select(sa.func.count())
        .select_from(ConnectorSyncJob)
        .join(ConnectorSource, ConnectorSource.id == ConnectorSyncJob.source_id)
        .join(ConnectorAccount, ConnectorAccount.id == ConnectorSource.account_id)
        .where(ConnectorAccount.user_id == uuid.UUID(user_id))
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
