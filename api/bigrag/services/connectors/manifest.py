from __future__ import annotations

from typing import Any

from bigrag.db.models import (
    Collection,
    ConnectorDocument,
    ConnectorSource,
    ConnectorSyncJob,
    Document,
)
from bigrag.services.connectors.types import (
    ConnectorSyncCounters,
    DownloadedConnectorFile,
    RemoteConnectorFile,
)


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
        "vector_store_provider": collection.vector_store_provider,
        "tenant_field": collection.tenant_field,
        "metadata_schema": collection.metadata_schema,
    }


def remote_signature(remote: RemoteConnectorFile) -> str | None:
    return remote.md5_checksum or remote.version


def manifest_remote_unchanged(
    manifest: ConnectorDocument | None,
    existing_doc: Document | None,
    remote: RemoteConnectorFile,
) -> bool:
    if manifest is None or existing_doc is None or existing_doc.status == "failed":
        return False
    signature = remote_signature(remote)
    old_signature = manifest.remote_checksum or manifest.remote_version
    return bool(signature and old_signature and signature == old_signature)


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


def update_manifest_remote(manifest: ConnectorDocument, remote: RemoteConnectorFile) -> None:
    manifest.remote_name = remote.name
    manifest.remote_mime_type = remote.mime_type
    manifest.remote_checksum = remote.md5_checksum
    manifest.remote_version = remote.version
    manifest.remote_modified_time = remote.modified_time
    manifest.web_url = remote.web_url
    manifest.status = "active"


def update_manifest(manifest: ConnectorDocument, downloaded: DownloadedConnectorFile) -> None:
    remote = downloaded.remote
    update_manifest_remote(manifest, remote)
    manifest.content_hash = downloaded.content_hash


def apply_counters(job: ConnectorSyncJob, counters: ConnectorSyncCounters) -> None:
    job.total_found = counters.found
    job.total_created = counters.created
    job.total_updated = counters.updated
    job.total_skipped = counters.skipped
    job.total_deleted = counters.deleted
    job.total_failed = counters.failed
    job.details = {**dict(job.details or {}), "errors": counters.errors}
