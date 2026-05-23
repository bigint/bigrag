from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

ConnectorProvider = Literal["s3"]
ConnectorSourceStatus = Literal["idle", "syncing", "error"]
ConnectorSourceType = Literal["prefix"]
ConnectorSyncTrigger = Literal["initial", "manual", "scheduled"]
ConnectorSyncStatus = Literal["pending", "running", "complete", "failed"]
ConnectorSyncProgressPhase = Literal[
    "queued",
    "authenticating",
    "scanning",
    "syncing",
    "removing",
    "finalizing",
    "complete",
    "failed",
]


class CreateS3SourceBody(TypedDict):
    collection_name: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    prefix: NotRequired[str]
    region: NotRequired[str]
    endpoint_url: NotRequired[str | None]
    force_path_style: NotRequired[bool]
    session_token: NotRequired[str | None]
    schedule_enabled: NotRequired[bool]
    sync_interval_hours: NotRequired[int]
    metadata: NotRequired[dict[str, Any]]


class UpdateS3SourceBody(TypedDict, total=False):
    bucket: str | None
    prefix: str | None
    region: str | None
    endpoint_url: str | None
    force_path_style: bool | None
    access_key_id: str | None
    secret_access_key: str | None
    session_token: str | None
    schedule_enabled: bool | None
    sync_interval_hours: int | None
    metadata: dict[str, Any] | None


class S3Source(TypedDict):
    id: str
    provider: ConnectorProvider
    collection_name: str
    bucket: str
    prefix: str
    region: str
    endpoint_url: str | None
    force_path_style: bool
    has_credentials: bool
    root_id: str
    root_name: str
    source_type: ConnectorSourceType
    status: ConnectorSourceStatus
    schedule_enabled: bool
    sync_interval_hours: int
    last_sync_at: str | None
    next_sync_at: str | None
    last_error: str | None
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


class S3SourceListResponse(TypedDict):
    sources: list[S3Source]
    total: int


class ConnectorSyncProgressCounts(TypedDict):
    created: int
    updated: int
    skipped: int
    deleted: int
    failed: int


class ConnectorSyncProgress(TypedDict):
    phase: ConnectorSyncProgressPhase
    message: str
    current_item_name: str | None
    current_item_id: str | None
    progress_percent: int
    processed_items: int
    total_items: int
    counts: ConnectorSyncProgressCounts


class ConnectorSyncJobDetails(TypedDict, total=False):
    errors: list[dict[str, str]]
    progress: ConnectorSyncProgress


class S3SyncJob(TypedDict):
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
    error_message: str | None
    details: ConnectorSyncJobDetails
    started_at: str | None
    completed_at: str | None
    created_at: str
    updated_at: str


class S3SyncJobListResponse(TypedDict):
    jobs: list[S3SyncJob]
    total: int
