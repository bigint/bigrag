from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ConnectorProvider = str
ConnectorAccountStatus = Literal["pending", "connected", "needs_reauth", "revoked"]
ConnectorSourceStatus = Literal["idle", "syncing", "needs_reauth", "error"]
ConnectorSourceType = Literal["file", "folder"]
ConnectorSyncTrigger = Literal["initial", "manual", "scheduled"]
ConnectorSyncStatus = Literal["pending", "running", "complete", "failed"]


class ConnectorConfigResponse(BaseModel):
    provider: ConnectorProvider
    configured: bool
    enabled: bool
    client_id: str
    has_client_secret: bool
    callback_url: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UpdateConnectorConfigRequest(BaseModel):
    enabled: bool = True
    client_id: str = Field(default="", max_length=500)
    client_secret: str | None = Field(default=None, max_length=5000)


class ConnectorAccountResponse(BaseModel):
    provider: ConnectorProvider
    configured: bool
    connected: bool
    status: ConnectorAccountStatus | None = None
    email: str | None = None
    scopes: list[str] = Field(default_factory=list)
    token_expires_at: datetime | None = None
    last_connected_at: datetime | None = None


class ConnectorFileResponse(BaseModel):
    id: str
    name: str
    mime_type: str
    source_type: ConnectorSourceType
    modified_time: datetime | None = None
    size: int | None = None
    web_url: str | None = None
    sync_supported: bool
    unsupported_reason: str | None = None


class ConnectorFileListResponse(BaseModel):
    provider: ConnectorProvider
    parent_id: str
    query: str
    files: list[ConnectorFileResponse]
    next_page_token: str | None = None


class CreateConnectorSourceRequest(BaseModel):
    collection_name: str = Field(min_length=1, max_length=120)
    root_id: str = Field(min_length=1, max_length=500)
    root_name: str = Field(min_length=1, max_length=500)
    root_mime_type: str = Field(default="", max_length=300)
    source_type: ConnectorSourceType | None = None
    metadata: dict = Field(default_factory=dict)


class UpdateConnectorSourceRequest(BaseModel):
    schedule_enabled: bool | None = None
    sync_interval_hours: int | None = Field(default=None, ge=1, le=24 * 30)


class ConnectorSourceResponse(BaseModel):
    id: str
    provider: ConnectorProvider
    collection_name: str
    root_id: str
    root_name: str
    root_mime_type: str
    source_type: ConnectorSourceType
    status: ConnectorSourceStatus
    schedule_enabled: bool
    sync_interval_hours: int
    last_sync_at: datetime | None = None
    next_sync_at: datetime | None = None
    last_error: str | None = None
    account_email: str | None = None
    metadata: dict
    created_at: datetime
    updated_at: datetime


class ConnectorSourceListResponse(BaseModel):
    sources: list[ConnectorSourceResponse]
    total: int


class ConnectorSyncJobResponse(BaseModel):
    id: str
    provider: ConnectorProvider
    source_id: str | None
    trigger: ConnectorSyncTrigger
    status: ConnectorSyncStatus
    total_found: int
    total_created: int
    total_updated: int
    total_skipped: int
    total_deleted: int
    total_failed: int
    error_message: str | None = None
    details: dict
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ConnectorSyncJobListResponse(BaseModel):
    jobs: list[ConnectorSyncJobResponse]
    total: int
