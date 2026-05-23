from __future__ import annotations

from typing import Any

from bigrag.db.models import ConnectorSource
from bigrag.services.connector_core import run_due_syncs, sync_connector_job
from bigrag.services.connectors.s3_client import download_s3_object, list_s3_objects
from bigrag.services.connectors.s3_sources import start_s3_sync_job
from bigrag.services.connectors.s3_types import S3_PROVIDER, s3_object_metadata
from bigrag.services.connectors.types import DownloadedConnectorFile, RemoteConnectorFile


class S3SyncAdapter:
    provider = S3_PROVIDER
    partial_failure_message = "Some S3 objects failed to sync"

    async def iter_files(
        self,
        session: Any,
        *,
        source: ConnectorSource,
    ) -> list[RemoteConnectorFile]:
        return await list_s3_objects(session, source=source)

    async def download(
        self,
        session: Any,
        *,
        source: ConnectorSource,
        remote: RemoteConnectorFile,
    ) -> DownloadedConnectorFile:
        return await download_s3_object(session, source=source, remote=remote)

    def metadata(self, *, source: ConnectorSource, remote: RemoteConnectorFile) -> dict[str, Any]:
        return s3_object_metadata(source=source, remote=remote)


s3_sync_adapter = S3SyncAdapter()


async def sync_s3_job(job_id: str) -> None:
    await sync_connector_job(job_id, s3_sync_adapter)


async def run_due_s3_syncs(limit: int = 10) -> int:
    return await run_due_syncs(
        provider=S3_PROVIDER,
        start_sync_job=start_s3_sync_job,
        limit=limit,
    )
