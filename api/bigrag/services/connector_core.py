from __future__ import annotations

import asyncio
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

from bigrag.db.engine import session_factory
from bigrag.db.models import (
    Collection,
    ConnectorAccount,
    ConnectorDocument,
    ConnectorProviderConfig,
    ConnectorSource,
    ConnectorSyncJob,
    Document,
)
from bigrag.logging import get_logger
from bigrag.routers._documents import (
    prepare_document_metadata,
    recount_collection_documents,
)
from bigrag.services import collection_cache
from bigrag.services.file_validation import InvalidFileContentError, validate_upload
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.storage import get_storage
from bigrag.services.vector_store import vector_store
from bigrag.utils import safe_create_task

logger = get_logger("bigrag.connectors")


class ConnectorError(RuntimeError):
    pass


class ConnectorConfigError(ConnectorError):
    pass


class ConnectorAuthError(ConnectorError):
    pass


class ConnectorNotFoundError(ConnectorError):
    pass


@dataclass(frozen=True)
class RemoteConnectorFile:
    id: str
    name: str
    mime_type: str
    modified_time: datetime | None = None
    md5_checksum: str | None = None
    size: int | None = None
    version: str | None = None
    web_url: str | None = None


@dataclass(frozen=True)
class DownloadedConnectorFile:
    remote: RemoteConnectorFile
    filename: str
    file_ext: str
    content: bytes
    content_hash: str


@dataclass
class ConnectorSyncCounters:
    found: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    deleted: int = 0
    failed: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def add_error(self, remote_id: str, name: str, error: str) -> None:
        self.failed += 1
        if len(self.errors) < 50:
            self.errors.append({"remote_id": remote_id, "name": name, "error": error})


class ConnectorSyncAdapter(Protocol):
    provider: str
    not_configured_message: str
    reauth_message: str
    partial_failure_message: str

    async def access_token_for_account(
        self,
        session: Any,
        *,
        config: ConnectorProviderConfig,
        account: ConnectorAccount,
    ) -> str: ...

    async def iter_files(
        self,
        *,
        access_token: str,
        source: ConnectorSource,
    ) -> list[RemoteConnectorFile]: ...

    async def download(
        self,
        *,
        access_token: str,
        remote: RemoteConnectorFile,
    ) -> DownloadedConnectorFile: ...

    def metadata(
        self,
        *,
        source: ConnectorSource,
        remote: RemoteConnectorFile,
    ) -> dict[str, Any]: ...


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def next_sync_at(source: ConnectorSource, *, from_time: datetime | None = None) -> datetime | None:
    if not source.schedule_enabled:
        return None
    interval = max(1, int(source.sync_interval_hours or 24))
    return (from_time or utcnow()) + timedelta(hours=interval)


def configured(config: ConnectorProviderConfig | None) -> bool:
    return bool(config and config.enabled and config.client_id and config.client_secret)


async def get_provider_config(session: Any, provider: str) -> ConnectorProviderConfig | None:
    return await session.scalar(
        sa.select(ConnectorProviderConfig).where(ConnectorProviderConfig.provider == provider)
    )


def config_public(
    config: ConnectorProviderConfig | None,
    *,
    provider: str,
    callback_url: str,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "configured": configured(config),
        "enabled": bool(config.enabled) if config else False,
        "client_id": config.client_id if config else "",
        "has_client_secret": bool(config and config.client_secret),
        "callback_url": callback_url,
        "created_at": config.created_at if config else None,
        "updated_at": config.updated_at if config else None,
    }


async def upsert_provider_config(
    session: Any,
    *,
    provider: str,
    enabled: bool,
    client_id: str,
    client_secret: str | None,
) -> ConnectorProviderConfig:
    existing = await get_provider_config(session, provider)
    values = {
        "provider": provider,
        "enabled": enabled,
        "client_id": client_id.strip(),
    }
    if client_secret is not None:
        values["client_secret"] = client_secret.strip() or None
    elif existing is not None:
        values["client_secret"] = existing.client_secret

    stmt = pg_insert(ConnectorProviderConfig).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ConnectorProviderConfig.provider],
        set_={
            "enabled": stmt.excluded.enabled,
            "client_id": stmt.excluded.client_id,
            "client_secret": stmt.excluded.client_secret,
            "updated_at": sa.func.now(),
        },
    ).returning(ConnectorProviderConfig)
    config = (await session.execute(stmt)).scalar_one()
    await session.commit()
    await session.refresh(config)
    return config


async def get_connector_account(
    session: Any,
    *,
    provider: str,
    user_id: str | uuid.UUID,
) -> ConnectorAccount | None:
    return await session.scalar(
        sa.select(ConnectorAccount)
        .where(ConnectorAccount.provider == provider)
        .where(ConnectorAccount.user_id == uuid.UUID(str(user_id)))
    )


def account_public(
    *,
    provider: str,
    config: ConnectorProviderConfig | None,
    account: ConnectorAccount | None,
    has_required_scope: Callable[[ConnectorAccount | None], bool],
) -> dict[str, Any]:
    scope_ok = has_required_scope(account)
    status = account.status if account else None
    if account and account.status == "connected" and not scope_ok:
        status = "needs_reauth"
    return {
        "provider": provider,
        "configured": configured(config),
        "connected": bool(
            account and account.status == "connected" and account.refresh_token and scope_ok
        ),
        "status": status,
        "email": account.account_email if account else None,
        "scopes": list(account.scopes or []) if account else [],
        "token_expires_at": account.token_expires_at if account else None,
        "last_connected_at": account.last_connected_at if account else None,
    }


async def prepare_oauth_account(
    session: Any,
    *,
    provider: str,
    user_id: str,
    redirect_path: str,
    redirect_origin: str | None,
) -> tuple[ConnectorAccount, str]:
    state = secrets.token_urlsafe(32)
    user_uuid = uuid.UUID(user_id)
    account = await get_connector_account(session, provider=provider, user_id=user_uuid)
    if account is None:
        account = ConnectorAccount(
            provider=provider,
            user_id=user_uuid,
            status="pending",
        )
        session.add(account)
    account.oauth_state = state
    account.status = "pending" if account.status != "connected" else account.status
    account.meta = {
        **dict(account.meta or {}),
        "redirect_origin": redirect_origin,
        "redirect_path": redirect_path or "/",
    }
    await session.commit()
    return account, state


def oauth_redirect_url(account: ConnectorAccount, path: str) -> str:
    origin = str((account.meta or {}).get("redirect_origin") or "").rstrip("/")
    if not origin:
        return path
    return f"{origin}{path}"


async def oauth_error_redirect_url(
    session: Any,
    *,
    provider: str,
    user_id: str,
    state: str | None,
    path: str,
) -> str:
    if not state:
        return path
    account = await get_connector_account(session, provider=provider, user_id=user_id)
    if account is None or account.oauth_state != state:
        return path
    return oauth_redirect_url(account, path)


async def disconnect_account(
    session: Any,
    *,
    provider: str,
    user_id: str,
    source_error: str,
) -> None:
    account = await get_connector_account(session, provider=provider, user_id=user_id)
    if account is None:
        return
    account.status = "revoked"
    account.access_token = None
    account.refresh_token = None
    account.token_expires_at = None
    account.oauth_state = None
    await session.execute(
        sa.update(ConnectorSource)
        .where(ConnectorSource.account_id == account.id)
        .values(status="needs_reauth", last_error=source_error)
    )
    await session.commit()


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
    await session.delete(source)
    await session.commit()


async def list_sync_jobs(
    session: Any,
    *,
    provider: str,
    user_id: str,
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
    rows = (await session.scalars(stmt)).all()
    total = await session.scalar(count_stmt)
    return [sync_job_public(provider, job) for job in rows], total or 0


class ConnectorScheduler:
    def __init__(
        self,
        *,
        provider: str,
        start_sync_job: Callable[[str], None],
        interval_seconds: int = 60,
    ) -> None:
        self.provider = provider
        self.start_sync_job = start_sync_job
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = safe_create_task(self._loop(), name=f"{self.provider}_scheduler")
        logger.info(
            "connector: scheduler started",
            provider=self.provider,
            interval_seconds=self.interval_seconds,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("connector: scheduler stopped", provider=self.provider)

    async def _loop(self) -> None:
        while self._running:
            try:
                await run_due_syncs(provider=self.provider, start_sync_job=self.start_sync_job)
            except Exception as exc:
                logger.warning(
                    "connector: scheduler tick failed",
                    provider=self.provider,
                    error=str(exc),
                )
            await asyncio.sleep(self.interval_seconds)


async def run_due_syncs(
    *,
    provider: str,
    start_sync_job: Callable[[str], None],
    limit: int = 10,
) -> int:
    from bigrag.services.maintenance import is_active

    if await is_active():
        return 0
    job_ids: list[str] = []
    async with session_factory()() as session:
        rows = (
            await session.scalars(
                sa.select(ConnectorSource)
                .where(ConnectorSource.provider == provider)
                .where(ConnectorSource.schedule_enabled.is_(True))
                .where(ConnectorSource.next_sync_at.is_not(None))
                .where(ConnectorSource.next_sync_at <= utcnow())
                .where(ConnectorSource.status != "syncing")
                .order_by(ConnectorSource.next_sync_at.asc())
                .limit(limit)
            )
        ).all()
        for source in rows:
            job = await create_sync_job(
                session,
                provider=provider,
                source=source,
                trigger="scheduled",
                user_id=None,
                commit=False,
            )
            await session.flush()
            if job.status == "pending" and job.started_at is None:
                job_ids.append(str(job.id))
        await session.commit()
    for job_id in job_ids:
        start_sync_job(job_id)
    return len(job_ids)


async def sync_connector_job(job_id: str, adapter: ConnectorSyncAdapter) -> None:
    counters = ConnectorSyncCounters()
    now = utcnow()
    async with session_factory()() as session:
        job = await session.get(ConnectorSyncJob, uuid.UUID(job_id))
        if job is None or job.source_id is None:
            return
        source = await session.get(ConnectorSource, job.source_id)
        if source is None or source.provider != adapter.provider:
            return
        account = await session.get(ConnectorAccount, source.account_id)
        config = await get_provider_config(session, adapter.provider)
        collection = await session.get(Collection, source.collection_id)

        job.status = "running"
        job.started_at = now
        source.status = "syncing"
        source.last_error = None
        await session.commit()

        if account is None or config is None or not configured(config) or collection is None:
            await fail_sync(
                session,
                job=job,
                source=source,
                message=adapter.not_configured_message,
            )
            return

        try:
            access_token = await adapter.access_token_for_account(
                session,
                config=config,
                account=account,
            )
            try:
                remotes = await adapter.iter_files(access_token=access_token, source=source)
            except ConnectorNotFoundError:
                remotes = []

            counters.found = len(remotes)
            seen_remote_ids = {remote.id for remote in remotes}
            manifests = {
                manifest.remote_id: manifest
                for manifest in (
                    await session.scalars(
                        sa.select(ConnectorDocument).where(ConnectorDocument.source_id == source.id)
                    )
                ).all()
            }

            for remote in remotes:
                manifest = manifests.get(remote.id)
                try:
                    downloaded = await adapter.download(access_token=access_token, remote=remote)
                    await sync_downloaded_file(
                        session,
                        adapter=adapter,
                        source=source,
                        collection=collection,
                        manifest=manifest,
                        downloaded=downloaded,
                        counters=counters,
                    )
                except (InvalidFileContentError, ValueError) as exc:
                    counters.add_error(remote.id, remote.name, str(exc))
                except Exception as exc:
                    logger.warning(
                        "connector: file sync failed",
                        provider=adapter.provider,
                        source_id=str(source.id),
                        remote_id=remote.id,
                        error_type=exc.__class__.__name__,
                        error=str(exc),
                    )
                    counters.add_error(remote.id, remote.name, str(exc))

            missing = [
                manifest
                for remote_id, manifest in manifests.items()
                if remote_id not in seen_remote_ids
            ]
            for manifest in missing:
                await delete_synced_document(
                    session,
                    source=source,
                    manifest=manifest,
                    counters=counters,
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
            await session.commit()
            await collection_cache.invalidate(source.collection_name)
            await invalidate_collection_query_cache(source.collection_name)
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
        except ConnectorAuthError as exc:
            account.status = "needs_reauth"
            source.status = "needs_reauth"
            source.last_error = adapter.reauth_message
            await fail_sync(session, job=job, source=source, message=str(exc))
        except Exception as exc:
            logger.exception(
                "connector: sync job failed",
                provider=adapter.provider,
                job_id=job_id,
            )
            await fail_sync(session, job=job, source=source, message=str(exc))


async def sync_downloaded_file(
    session: Any,
    *,
    adapter: ConnectorSyncAdapter,
    source: ConnectorSource,
    collection: Collection,
    manifest: ConnectorDocument | None,
    downloaded: DownloadedConnectorFile,
    counters: ConnectorSyncCounters,
) -> None:
    remote = downloaded.remote
    existing_doc = await session.get(Document, manifest.document_id) if manifest else None
    if (
        manifest is not None
        and existing_doc is not None
        and existing_doc.status != "failed"
        and manifest_unchanged(manifest, downloaded)
    ):
        counters.skipped += 1
        manifest.remote_name = remote.name
        manifest.remote_mime_type = remote.mime_type
        manifest.web_url = remote.web_url
        return

    validate_upload(downloaded.content, downloaded.file_ext)
    collection_dict = collection_dict_for_sync(collection)
    metadata = prepare_document_metadata(
        collection_dict,
        adapter.metadata(source=source, remote=remote),
    )
    storage = get_storage()

    if manifest is None:
        doc_id = uuid.uuid4()
        storage_key = f"{source.collection_name}/{doc_id}{downloaded.file_ext}"
        await storage.put(storage_key, downloaded.content)
        doc = Document(
            id=doc_id,
            collection_id=collection.id,
            filename=downloaded.filename,
            file_type=downloaded.file_ext.lstrip("."),
            file_size=len(downloaded.content),
            file_path=storage_key,
            content_hash=downloaded.content_hash,
            meta=metadata,
        )
        session.add(doc)
        await session.flush()
        session.add(manifest_for_download(source=source, doc=doc, downloaded=downloaded))
        counters.created += 1
    else:
        doc = existing_doc
        if doc is None:
            doc_id = uuid.uuid4()
            storage_key = f"{source.collection_name}/{doc_id}{downloaded.file_ext}"
            await storage.put(storage_key, downloaded.content)
            doc = Document(
                id=doc_id,
                collection_id=collection.id,
                filename=downloaded.filename,
                file_type=downloaded.file_ext.lstrip("."),
                file_size=len(downloaded.content),
                file_path=storage_key,
                content_hash=downloaded.content_hash,
                meta=metadata,
            )
            session.add(doc)
            await session.flush()
            session.add(manifest_for_download(source=source, doc=doc, downloaded=downloaded))
            counters.created += 1
        else:
            await ingestion_queue.cancel_documents([str(doc.id)])
            await vector_store.delete_by_document(source.collection_name, str(doc.id))
            old_path = doc.file_path
            storage_key = f"{source.collection_name}/{doc.id}{downloaded.file_ext}"
            await storage.put(storage_key, downloaded.content)
            if old_path != storage_key:
                await storage.delete(old_path)
            doc.filename = downloaded.filename
            doc.file_type = downloaded.file_ext.lstrip(".")
            doc.file_size = len(downloaded.content)
            doc.file_path = storage_key
            doc.content_hash = downloaded.content_hash
            doc.status = "pending"
            doc.chunk_count = 0
            doc.token_count = 0
            doc.error_message = None
            doc.meta = metadata
            update_manifest(manifest, downloaded)
            counters.updated += 1

    await session.flush()
    await session.commit()
    try:
        await ingestion_queue.enqueue(
            create_ingestion_job(
                document_id=str(doc.id),
                file_path=doc.file_path,
                collection_name=source.collection_name,
                collection=collection_dict,
            )
        )
    except Exception as exc:
        doc.status = "failed"
        doc.error_message = f"enqueue failed: {exc.__class__.__name__}: {exc}"
        await session.commit()
        raise


def collection_dict_for_sync(collection: Collection) -> dict[str, Any]:
    return {
        "id": collection.id,
        "name": collection.name,
        "embedding_provider": collection.embedding_provider,
        "embedding_model": collection.embedding_model,
        "dimension": collection.dimension,
        "chunk_size": collection.chunk_size,
        "chunk_overlap": collection.chunk_overlap,
        "chunk_strategy": collection.chunk_strategy or "paragraph",
        "tenant_field": collection.tenant_field,
        "metadata_schema": collection.metadata_schema,
    }


def remote_signature(remote: RemoteConnectorFile) -> str | None:
    return remote.md5_checksum or remote.version


def manifest_unchanged(
    manifest: ConnectorDocument,
    downloaded: DownloadedConnectorFile,
) -> bool:
    remote = downloaded.remote
    signature = remote_signature(remote)
    old_signature = manifest.remote_checksum or manifest.remote_version
    if signature and old_signature and signature == old_signature:
        return True
    return bool(manifest.content_hash and manifest.content_hash == downloaded.content_hash)


def manifest_for_download(
    *,
    source: ConnectorSource,
    doc: Document,
    downloaded: DownloadedConnectorFile,
) -> ConnectorDocument:
    remote = downloaded.remote
    return ConnectorDocument(
        source_id=source.id,
        document_id=doc.id,
        remote_id=remote.id,
        remote_name=remote.name,
        remote_mime_type=remote.mime_type,
        remote_checksum=remote.md5_checksum,
        remote_version=remote.version,
        remote_modified_time=remote.modified_time,
        content_hash=downloaded.content_hash,
        web_url=remote.web_url,
        status="active",
    )


def update_manifest(manifest: ConnectorDocument, downloaded: DownloadedConnectorFile) -> None:
    remote = downloaded.remote
    manifest.remote_name = remote.name
    manifest.remote_mime_type = remote.mime_type
    manifest.remote_checksum = remote.md5_checksum
    manifest.remote_version = remote.version
    manifest.remote_modified_time = remote.modified_time
    manifest.content_hash = downloaded.content_hash
    manifest.web_url = remote.web_url
    manifest.status = "active"


async def delete_synced_document(
    session: Any,
    *,
    source: ConnectorSource,
    manifest: ConnectorDocument,
    counters: ConnectorSyncCounters,
) -> None:
    doc = await session.get(Document, manifest.document_id)
    if doc is not None:
        await ingestion_queue.cancel_documents([str(doc.id)])
        await vector_store.delete_by_document(source.collection_name, str(doc.id))
        await get_storage().delete(doc.file_path)
        await session.delete(doc)
    await session.delete(manifest)
    counters.deleted += 1


def apply_counters(job: ConnectorSyncJob, counters: ConnectorSyncCounters) -> None:
    job.total_found = counters.found
    job.total_created = counters.created
    job.total_updated = counters.updated
    job.total_skipped = counters.skipped
    job.total_deleted = counters.deleted
    job.total_failed = counters.failed
    job.details = {"errors": counters.errors}


async def fail_sync(
    session: Any,
    *,
    job: ConnectorSyncJob,
    source: ConnectorSource,
    message: str,
) -> None:
    job.status = "failed"
    job.error_message = message
    job.completed_at = utcnow()
    source.status = "needs_reauth" if source.status == "needs_reauth" else "error"
    source.last_error = message
    source.next_sync_at = next_sync_at(source)
    await session.commit()
