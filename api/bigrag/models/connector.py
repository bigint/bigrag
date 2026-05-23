from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ConnectorProvider = Literal["s3"]
ConnectorSourceStatus = Literal["idle", "syncing", "error"]
ConnectorSourceType = Literal["prefix"]
ConnectorSyncTrigger = Literal["initial", "manual", "scheduled"]
ConnectorSyncStatus = Literal["pending", "running", "complete", "failed"]


class CreateConnectorSourceRequest(BaseModel):
    collection_name: str = Field(min_length=1, max_length=120)
    bucket: str = Field(min_length=1, max_length=255)
    prefix: str = Field(default="", max_length=1024)
    region: str = Field(default="us-east-1", min_length=1, max_length=100)
    endpoint_url: str | None = Field(default=None, max_length=500)
    force_path_style: bool = False
    access_key_id: str = Field(min_length=1, max_length=500)
    secret_access_key: str = Field(min_length=1, max_length=5000)
    session_token: str | None = Field(default=None, max_length=5000)
    schedule_enabled: bool = True
    sync_interval_hours: int = Field(default=24, ge=1, le=24 * 30)
    metadata: dict = Field(default_factory=dict)


class UpdateConnectorSourceRequest(BaseModel):
    bucket: str | None = Field(default=None, min_length=1, max_length=255)
    prefix: str | None = Field(default=None, max_length=1024)
    region: str | None = Field(default=None, min_length=1, max_length=100)
    endpoint_url: str | None = Field(default=None, max_length=500)
    force_path_style: bool | None = None
    access_key_id: str | None = Field(default=None, min_length=1, max_length=500)
    secret_access_key: str | None = Field(default=None, min_length=1, max_length=5000)
    session_token: str | None = Field(default=None, max_length=5000)
    schedule_enabled: bool | None = None
    sync_interval_hours: int | None = Field(default=None, ge=1, le=24 * 30)
    metadata: dict | None = None


class ConnectorSourceResponse(BaseModel):
    id: str
    provider: ConnectorProvider
    collection_name: str
    bucket: str
    prefix: str
    region: str
    endpoint_url: str | None = None
    force_path_style: bool
    has_credentials: bool
    root_id: str
    root_name: str
    source_type: ConnectorSourceType
    status: ConnectorSourceStatus
    schedule_enabled: bool
    sync_interval_hours: int
    last_sync_at: datetime | None = None
    next_sync_at: datetime | None = None
    last_error: str | None = None
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
