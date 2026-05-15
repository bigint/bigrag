from __future__ import annotations

from typing import Any

from bigrag.db.models import ConnectorAccount, ConnectorProviderConfig, ConnectorSource
from bigrag.services.connector_core import run_due_syncs, sync_connector_job
from bigrag.services.connectors.google_drive_auth import _access_token_for_account
from bigrag.services.connectors.google_drive_client import google_drive_client
from bigrag.services.connectors.google_drive_sources import start_google_sync_job
from bigrag.services.connectors.google_drive_types import (
    GOOGLE_PROVIDER,
    DownloadedDriveFile,
    RemoteDriveFile,
    _drive_metadata,
)


class GoogleDriveSyncAdapter:
    provider = GOOGLE_PROVIDER
    not_configured_message = "Google Drive connector is not configured"
    reauth_message = "Google account needs reconnection"
    partial_failure_message = "Some Drive files failed to sync"

    async def access_token_for_account(
        self,
        session,
        *,
        config: ConnectorProviderConfig,
        account: ConnectorAccount,
    ) -> str:
        return await _access_token_for_account(session, config=config, account=account)

    async def iter_files(
        self,
        *,
        access_token: str,
        source: ConnectorSource,
    ) -> list[RemoteDriveFile]:
        return await google_drive_client.iter_files(
            access_token=access_token,
            root_id=source.root_id,
            source_type=source.source_type,
        )

    async def download(
        self,
        *,
        access_token: str,
        remote: RemoteDriveFile,
    ) -> DownloadedDriveFile:
        return await google_drive_client.download(access_token, remote)

    def metadata(self, *, source: ConnectorSource, remote: RemoteDriveFile) -> dict[str, Any]:
        return _drive_metadata(source, remote)


google_drive_sync_adapter = GoogleDriveSyncAdapter()


async def sync_google_drive_job(job_id: str) -> None:
    await sync_connector_job(job_id, google_drive_sync_adapter)


async def run_due_google_syncs(limit: int = 10) -> int:
    return await run_due_syncs(
        provider=GOOGLE_PROVIDER,
        start_sync_job=start_google_sync_job,
        limit=limit,
    )
