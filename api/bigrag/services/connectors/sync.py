from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import (
    Collection,
    ConnectorAccount,
    ConnectorDocument,
    ConnectorSource,
    ConnectorSyncJob,
    Document,
)
from bigrag.logging import get_logger
from bigrag.routers._documents import prepare_document_metadata, recount_collection_documents
from bigrag.services import collection_cache
from bigrag.services.connectors.accounts import configured, get_provider_config
from bigrag.services.connectors.progress import update_sync_progress
from bigrag.services.connectors.time import next_sync_at, utcnow
from bigrag.services.connectors.types import (
    ConnectorAuthError,
    ConnectorNotFoundError,
    ConnectorSyncAdapter,
    ConnectorSyncCounters,
    DownloadedConnectorFile,
    RemoteConnectorFile,
)
from bigrag.services.file_validation import InvalidFileContentError, validate_upload
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.storage import get_storage
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.connectors")


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
        account = await session.get(ConnectorAccount, source.account_id)
        config = await get_provider_config(session, adapter.provider)
        collection = await session.get(Collection, source.collection_id)

        job.status = "running"
        job.started_at = now
        source.status = "syncing"
        source.last_error = None
        await update_sync_progress(
            session,
            job=job,
            counters=counters,
            phase="authenticating",
            message="Connecting to Google Drive",
        )

        if account is None or config is None or not configured(config) or collection is None:
            await fail_sync(
                session,
                job=job,
                source=source,
                message=adapter.not_configured_message,
                counters=counters,
            )
            return

        try:
            await ensure_writes_allowed()
            access_token = await adapter.access_token_for_account(
                session,
                config=config,
                account=account,
            )
            await update_sync_progress(
                session,
                job=job,
                counters=counters,
                phase="scanning",
                message="Scanning Drive files",
            )
            try:
                remotes = await adapter.iter_files(access_token=access_token, source=source)
            except ConnectorNotFoundError:
                remotes = []

            counters.found = len(remotes)
            await update_sync_progress(
                session,
                job=job,
                counters=counters,
                phase="syncing",
                message=f"Found {len(remotes)} Drive files",
                processed_items=0,
                total_items=len(remotes),
            )
            seen_remote_ids = {remote.id for remote in remotes}
            manifests = {
                manifest.remote_id: manifest
                for manifest in (
                    await session.scalars(
                        sa.select(ConnectorDocument).where(ConnectorDocument.source_id == source.id)
                    )
                ).all()
            }

            for index, remote in enumerate(remotes, start=1):
                manifest = manifests.get(remote.id)
                await update_sync_progress(
                    session,
                    job=job,
                    counters=counters,
                    phase="syncing",
                    message=f"Syncing {remote.name}",
                    current_item=remote,
                    processed_items=index - 1,
                    total_items=len(remotes),
                )
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
                await update_sync_progress(
                    session,
                    job=job,
                    counters=counters,
                    phase="syncing",
                    message=f"Synced {index} of {len(remotes)} Drive files",
                    current_item=remote,
                    processed_items=index,
                    total_items=len(remotes),
                )

            missing = [
                manifest
                for remote_id, manifest in manifests.items()
                if remote_id not in seen_remote_ids
            ]
            await update_sync_progress(
                session,
                job=job,
                counters=counters,
                phase="removing",
                message="Checking for removed Drive files",
                processed_items=0,
                total_items=len(missing),
            )
            for index, manifest in enumerate(missing, start=1):
                await update_sync_progress(
                    session,
                    job=job,
                    counters=counters,
                    phase="removing",
                    message=f"Removing {manifest.remote_name}",
                    current_item=manifest,
                    processed_items=index - 1,
                    total_items=len(missing),
                )
                await delete_synced_document(
                    session,
                    collection=collection,
                    source=source,
                    manifest=manifest,
                    counters=counters,
                )
                await update_sync_progress(
                    session,
                    job=job,
                    counters=counters,
                    phase="removing",
                    message=f"Removed {index} of {len(missing)} missing Drive files",
                    current_item=manifest,
                    processed_items=index,
                    total_items=len(missing),
                )

            await update_sync_progress(
                session,
                job=job,
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
                counters=counters,
                phase="complete" if counters.failed == 0 else "failed",
                message=(
                    "Drive sync complete. Documents queued for ingestion."
                    if counters.failed == 0
                    else adapter.partial_failure_message
                ),
                processed_items=counters.found + counters.deleted,
                total_items=counters.found + len(missing),
            )
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
            await fail_sync(session, job=job, source=source, message=str(exc), counters=counters)
        except Exception as exc:
            logger.exception(
                "connector: sync job failed",
                provider=adapter.provider,
                job_id=job_id,
            )
            await fail_sync(session, job=job, source=source, message=str(exc), counters=counters)


async def sync_downloaded_file(
    session: Any,
    *,
    adapter: ConnectorSyncAdapter,
    source: ConnectorSource,
    collection: Collection | None,
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
            await vector_store.delete_by_document(
                source.collection_name,
                str(doc.id),
                provider=getattr(collection, "vector_store_provider", "qdrant"),
            )
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
        "vector_store_provider": getattr(collection, "vector_store_provider", "qdrant"),
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
    collection: Collection,
    source: ConnectorSource,
    manifest: ConnectorDocument,
    counters: ConnectorSyncCounters,
) -> None:
    doc = await session.get(Document, manifest.document_id)
    if doc is not None:
        await ingestion_queue.cancel_documents([str(doc.id)])
        await vector_store.delete_by_document(
            source.collection_name,
            str(doc.id),
            provider=getattr(collection, "vector_store_provider", "qdrant"),
        )
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
    job.details = {**dict(job.details or {}), "errors": counters.errors}


async def fail_sync(
    session: Any,
    *,
    job: ConnectorSyncJob,
    source: ConnectorSource,
    message: str,
    counters: ConnectorSyncCounters | None = None,
) -> None:
    counters = counters or ConnectorSyncCounters()
    completed = utcnow()
    job.status = "failed"
    job.error_message = message
    job.completed_at = completed
    apply_counters(job, counters)
    if source.status != "needs_reauth":
        source.status = "error"
    source.last_sync_at = completed
    source.next_sync_at = next_sync_at(source, from_time=completed)
    source.last_error = message
    await update_sync_progress(
        session,
        job=job,
        counters=counters,
        phase="failed",
        message=message,
    )
