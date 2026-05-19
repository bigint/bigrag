from __future__ import annotations

from typing import Any

from bigrag.db.models import Collection, ConnectorDocument, ConnectorSource, Document
from bigrag.ids import uuid7
from bigrag.services.connectors.manifest import (
    collection_dict_for_sync,
    manifest_for_download,
    manifest_unchanged,
    update_manifest,
)
from bigrag.services.connectors.types import (
    ConnectorSyncAdapter,
    ConnectorSyncCounters,
    DownloadedConnectorFile,
)
from bigrag.services.documents import prepare_document_metadata
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.file_validation import validate_upload
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
from bigrag.services.storage import get_storage
from bigrag.services.vector_store import vector_store


async def sync_downloaded_file(
    session: Any,
    *,
    adapter: ConnectorSyncAdapter,
    source: ConnectorSource,
    collection: Collection | None,
    manifest: ConnectorDocument | None,
    existing_doc: Document | None,
    downloaded: DownloadedConnectorFile,
    counters: ConnectorSyncCounters,
) -> None:
    remote = downloaded.remote
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

    await validate_upload(downloaded.path, downloaded.file_ext)
    collection_dict = collection_dict_for_sync(collection)
    metadata = prepare_document_metadata(
        collection_dict,
        adapter.metadata(source=source, remote=remote),
    )
    storage = get_storage()

    async def _put_downloaded(storage_key: str) -> None:
        with downloaded.path.open("rb") as fh:
            await storage.put_stream(storage_key, fh, size=downloaded.file_size)

    if manifest is None:
        doc_id = uuid7()
        storage_key = f"{source.collection_name}/{doc_id}{downloaded.file_ext}"
        await _put_downloaded(storage_key)
        doc = Document(
            id=doc_id,
            collection_id=collection.id,
            filename=downloaded.filename,
            file_type=downloaded.file_ext.lstrip("."),
            file_size=downloaded.file_size,
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
            doc_id = uuid7()
            storage_key = f"{source.collection_name}/{doc_id}{downloaded.file_ext}"
            await _put_downloaded(storage_key)
            doc = Document(
                id=doc_id,
                collection_id=collection.id,
                filename=downloaded.filename,
                file_type=downloaded.file_ext.lstrip("."),
                file_size=downloaded.file_size,
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
                provider=collection.vector_store_provider,
            )
            old_path = doc.file_path
            storage_key = f"{source.collection_name}/{doc.id}{downloaded.file_ext}"
            await _put_downloaded(storage_key)
            if old_path != storage_key:
                await storage.delete(old_path)
            doc.filename = downloaded.filename
            doc.file_type = downloaded.file_ext.lstrip(".")
            doc.file_size = downloaded.file_size
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
        doc.error_message = sanitize_message_text(f"enqueue failed: {type(exc).__name__}")
        await session.commit()
        raise


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
            provider=collection.vector_store_provider,
        )
        await get_storage().delete(doc.file_path)
        await session.delete(doc)
    await session.delete(manifest)
    counters.deleted += 1
