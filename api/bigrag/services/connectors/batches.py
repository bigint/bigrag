from __future__ import annotations

import asyncio
from typing import Any

import sqlalchemy as sa

from bigrag.db.models import (
    Collection,
    ConnectorDocument,
    ConnectorSource,
    Document,
)
from bigrag.logging import get_logger
from bigrag.services.connectors.documents import sync_downloaded_file
from bigrag.services.connectors.manifest import manifest_remote_unchanged, update_manifest_remote
from bigrag.services.connectors.types import (
    ConnectorSyncAdapter,
    ConnectorSyncCounters,
    RemoteConnectorFile,
)
from bigrag.services.file_validation import InvalidFileContentError
from bigrag.services.queue import QueueFullError

logger = get_logger("bigrag.connectors")

DOWNLOAD_BATCH_SIZE = 4


async def sync_page(
    session: Any,
    *,
    adapter: ConnectorSyncAdapter,
    source: ConnectorSource,
    collection: Collection,
    remotes: list[RemoteConnectorFile],
    manifests: dict[str, ConnectorDocument],
    counters: ConnectorSyncCounters,
) -> None:
    async def _download(remote: RemoteConnectorFile):
        return await adapter.download(session, source=source, remote=remote)

    for batch_start in range(0, len(remotes), DOWNLOAD_BATCH_SIZE):
        batch = remotes[batch_start : batch_start + DOWNLOAD_BATCH_SIZE]
        batch_manifests = {
            remote.id: manifests.get(remote.id)
            for remote in batch
            if manifests.get(remote.id) is not None
        }
        batch_document_ids = [manifest.document_id for manifest in batch_manifests.values()]
        existing_docs = {}
        if batch_document_ids:
            existing_docs = {
                doc.id: doc
                for doc in (
                    await session.scalars(
                        sa.select(Document).where(Document.id.in_(batch_document_ids))
                    )
                ).all()
            }
        skipped_remote_ids = set()
        download_targets = []
        for remote in batch:
            manifest = manifests.get(remote.id)
            existing_doc = existing_docs.get(manifest.document_id) if manifest else None
            if manifest_remote_unchanged(manifest, existing_doc, remote):
                skipped_remote_ids.add(remote.id)
            else:
                download_targets.append(remote)
        batch_results = await asyncio.gather(
            *[_download(r) for r in download_targets], return_exceptions=True
        )
        downloaded_by_remote_id = {
            remote.id: result
            for remote, result in zip(download_targets, batch_results, strict=True)
        }
        for remote in batch:
            manifest = manifests.get(remote.id)
            existing_doc = existing_docs.get(manifest.document_id) if manifest else None
            downloaded = None
            try:
                if remote.id in skipped_remote_ids:
                    if manifest is not None:
                        update_manifest_remote(manifest, remote)
                    counters.skipped += 1
                else:
                    result = downloaded_by_remote_id[remote.id]
                    if isinstance(result, BaseException):
                        raise result
                    downloaded = result
                    await sync_downloaded_file(
                        session,
                        adapter=adapter,
                        source=source,
                        collection=collection,
                        manifest=manifest,
                        existing_doc=existing_doc,
                        downloaded=downloaded,
                        counters=counters,
                    )
            except QueueFullError:
                raise
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
            finally:
                if downloaded is not None:
                    try:
                        downloaded.path.unlink()
                    except OSError:
                        pass
