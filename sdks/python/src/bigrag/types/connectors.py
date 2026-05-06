"""Connector types."""

from __future__ import annotations

from typing import Literal

from bigrag.types._compat import Any, NotRequired, TypedDict

GoogleProvider = Literal["google_drive"]
ConnectorAccountStatus = Literal["pending", "connected", "needs_reauth", "revoked"]
ConnectorSourceStatus = Literal["idle", "syncing", "needs_reauth", "error"]
ConnectorSourceType = Literal["file", "folder"]
ConnectorSyncTrigger = Literal["initial", "manual", "scheduled"]
ConnectorSyncStatus = Literal["pending", "running", "complete", "failed"]


class GoogleConnectorConfig(TypedDict):
    provider: GoogleProvider
    configured: bool
    enabled: bool
    client_id: str
    has_client_secret: bool
    callback_url: str
    created_at: str | None
    updated_at: str | None


class UpdateGoogleConnectorConfigBody(TypedDict, total=False):
    enabled: bool
    client_id: str
    client_secret: str | None


class GoogleAccount(TypedDict):
    provider: GoogleProvider
    configured: bool
    connected: bool
    status: ConnectorAccountStatus | None
    email: str | None
    scopes: list[str]
    token_expires_at: str | None
    last_connected_at: str | None


class GoogleDriveFile(TypedDict):
    id: str
    name: str
    mime_type: str
    source_type: ConnectorSourceType
    modified_time: str | None
    size: int | None
    web_url: str | None
    sync_supported: bool
    unsupported_reason: str | None


class GoogleDriveFileListResponse(TypedDict):
    provider: GoogleProvider
    parent_id: str
    query: str
    files: list[GoogleDriveFile]
    next_page_token: str | None


class GoogleOAuthStartUrlResponse(TypedDict):
    auth_url: str


class CreateGoogleSourceBody(TypedDict):
    collection_name: str
    root_id: str
    root_name: str
    root_mime_type: NotRequired[str]
    source_type: NotRequired[ConnectorSourceType | None]
    metadata: NotRequired[dict[str, Any]]


class UpdateGoogleSourceBody(TypedDict, total=False):
    schedule_enabled: bool | None
    sync_interval_hours: int | None


class GoogleSource(TypedDict):
    id: str
    provider: GoogleProvider
    collection_name: str
    root_id: str
    root_name: str
    root_mime_type: str
    source_type: ConnectorSourceType
    status: ConnectorSourceStatus
    schedule_enabled: bool
    sync_interval_hours: int
    last_sync_at: str | None
    next_sync_at: str | None
    last_error: str | None
    account_email: str | None
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


class GoogleSourceListResponse(TypedDict):
    sources: list[GoogleSource]
    total: int


class GoogleSyncJob(TypedDict):
    id: str
    provider: GoogleProvider
    source_id: str | None
    trigger: ConnectorSyncTrigger
    status: ConnectorSyncStatus
    total_found: int
    total_created: int
    total_updated: int
    total_skipped: int
    total_deleted: int
    total_failed: int
    error_message: str | None
    details: dict[str, Any]
    started_at: str | None
    completed_at: str | None
    created_at: str
    updated_at: str


class GoogleSyncJobListResponse(TypedDict):
    jobs: list[GoogleSyncJob]
    total: int
