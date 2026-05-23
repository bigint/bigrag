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
    ConnectorSourceCredential,
    ConnectorSyncJob,
)
from bigrag.services import collection_cache
from bigrag.services.connectors.progress import sync_progress_details
from bigrag.services.connectors.time import next_sync_at, utcnow
from bigrag.services.retrieval import invalidate_collection_query_cache


def source_public(provider: str, source: ConnectorSource) -> dict[str, Any]:
    metadata = dict(source.meta or {})
    config = dict(metadata.get("s3") or {})
    return {
        "id": str(source.id),
        "provider": provider,
        "collection_name": source.collection_name,
        "bucket": config.get("bucket") or "",
        "prefix": config.get("prefix") or "",
        "region": config.get("region") or "us-east-1",
        "endpoint_url": config.get("endpoint_url"),
        "force_path_style": bool(config.get("force_path_style")),
        "has_credentials": bool(config.get("has_credentials")),
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


async def list_sources(
    session: Any,
    *,
    provider: str,
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
                message="S3 sync queued",
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
) -> tuple[ConnectorSource, ConnectorSyncJob]:
    collection = await session.scalar(
        sa.select(Collection).where(Collection.name == collection_name)
    )
    if collection is None:
        raise ValueError("Collection not found")

    metadata_dict = dict(metadata or {})
    source = ConnectorSource(
        provider=provider,
        collection_id=collection.id,
        collection_name=collection.name,
        tenant_id=_tenant_id(collection, metadata_dict),
        root_id=root_id,
        root_name=root_name,
        root_mime_type="",
        source_type="prefix",
        schedule_enabled=schedule_enabled,
        sync_interval_hours=sync_interval_hours,
        status="syncing",
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
            .where(ConnectorSource.collection_id == collection.id)
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
        commit=False,
    )
    await session.commit()
    await session.refresh(source)
    await session.refresh(job)
    if job.status == "pending" and job.started_at is None:
        start_sync_job(str(job.id))
    return source, job


async def upsert_source_credential(
    session: Any,
    *,
    source: ConnectorSource,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
    session_token: str | None = None,
    session_token_set: bool = False,
    region: str,
    endpoint_url: str | None,
    force_path_style: bool,
) -> ConnectorSourceCredential:
    credential = await session.scalar(
        sa.select(ConnectorSourceCredential).where(ConnectorSourceCredential.source_id == source.id)
    )
    if credential is None:
        if not access_key_id or not secret_access_key:
            raise ValueError("S3 access key ID and secret access key are required")
        credential = ConnectorSourceCredential(
            source_id=source.id,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            session_token=session_token,
            region=region,
            endpoint_url=endpoint_url,
            force_path_style=force_path_style,
        )
        session.add(credential)
        return credential
    if access_key_id is not None or secret_access_key is not None:
        if not access_key_id or not secret_access_key:
            raise ValueError("S3 access key ID and secret access key must be rotated together")
        credential.access_key_id = access_key_id
        credential.secret_access_key = secret_access_key
        credential.session_token = session_token
    elif session_token_set:
        credential.session_token = session_token
    credential.region = region
    credential.endpoint_url = endpoint_url
    credential.force_path_style = force_path_style
    return credential


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
    await collection_cache.invalidate(source.collection_name)


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


def _tenant_id(collection: Collection, metadata: dict[str, Any]) -> str | None:
    if collection.tenant_field:
        raw_tenant = metadata.get(collection.tenant_field)
        if isinstance(raw_tenant, str) and raw_tenant:
            return raw_tenant
    return None
