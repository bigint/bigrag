from __future__ import annotations

from typing import Any

from bigrag.db.models import ConnectorAccount, ConnectorSource, ConnectorSyncJob
from bigrag.services.connector_core import (
    configured,
    create_source,
    create_sync_job,
    delete_source,
    list_sources,
    source_public,
    sync_job_public,
    trigger_sync,
    update_source,
)
from bigrag.services.connectors.google_drive_auth import get_google_account, get_google_config
from bigrag.services.connectors.google_drive_types import (
    GOOGLE_FOLDER_MIME,
    GOOGLE_PROVIDER,
    GoogleDriveAuthError,
    GoogleDriveConfigError,
)
from bigrag.utils import safe_create_task


def google_source_public(row: tuple[ConnectorSource, ConnectorAccount]) -> dict[str, Any]:
    return source_public(GOOGLE_PROVIDER, row)


def google_sync_job_public(job: ConnectorSyncJob) -> dict[str, Any]:
    return sync_job_public(GOOGLE_PROVIDER, job)


async def list_google_sources(
    session,
    *,
    user_id: str,
    collection_name: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    return await list_sources(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        collection_name=collection_name,
    )


def _infer_source_type(root_mime_type: str) -> str:
    return "folder" if root_mime_type == GOOGLE_FOLDER_MIME else "file"


async def create_google_source(
    session,
    *,
    user_id: str,
    collection_name: str,
    root_id: str,
    root_name: str,
    root_mime_type: str,
    source_type: str | None,
    metadata: dict,
) -> tuple[ConnectorSource, ConnectorSyncJob]:
    config = await get_google_config(session)
    if not configured(config):
        raise GoogleDriveConfigError("Google Drive connector is not configured")
    account = await get_google_account(session, user_id)
    if account is None or account.status != "connected":
        raise GoogleDriveAuthError("Connect Google Drive before adding sources")

    return await create_source(
        session,
        provider=GOOGLE_PROVIDER,
        account=account,
        collection_name=collection_name,
        root_id=root_id,
        root_name=root_name,
        root_mime_type=root_mime_type,
        source_type=source_type,
        metadata=metadata,
        user_id=user_id,
        infer_source_type=_infer_source_type,
        start_sync_job=start_google_sync_job,
    )


async def create_google_sync_job(
    session,
    *,
    source: ConnectorSource,
    trigger: str,
    user_id: str | None,
    commit: bool = True,
) -> ConnectorSyncJob:
    return await create_sync_job(
        session,
        provider=GOOGLE_PROVIDER,
        source=source,
        trigger=trigger,
        user_id=user_id,
        commit=commit,
    )


def start_google_sync_job(job_id: str) -> None:
    from bigrag.services.connectors.google_drive_sync import sync_google_drive_job

    safe_create_task(sync_google_drive_job(job_id), name=f"google_drive_sync:{job_id}")


async def trigger_google_sync(
    session,
    *,
    user_id: str,
    source_id: str,
    trigger: str = "manual",
) -> ConnectorSyncJob:
    return await trigger_sync(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        source_id=source_id,
        not_found_message="Google Drive source not found",
        start_sync_job=start_google_sync_job,
        trigger=trigger,
    )


async def update_google_source(
    session,
    *,
    user_id: str,
    source_id: str,
    schedule_enabled: bool | None,
    sync_interval_hours: int | None,
) -> ConnectorSource:
    return await update_source(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        source_id=source_id,
        not_found_message="Google Drive source not found",
        schedule_enabled=schedule_enabled,
        sync_interval_hours=sync_interval_hours,
    )


async def delete_google_source(
    session,
    *,
    user_id: str,
    source_id: str,
) -> None:
    await delete_source(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        source_id=source_id,
        not_found_message="Google Drive source not found",
    )
