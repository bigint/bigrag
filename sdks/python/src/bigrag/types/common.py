from __future__ import annotations

from typing import NotRequired, TypedDict


class StatusResponse(TypedDict):
    status: str
    message: NotRequired[str]


class HealthResponse(TypedDict):
    status: str
    version: str


class ReadinessResponse(TypedDict):
    status: str
    version: str
    postgres: bool
    vector_store: bool
    redis: bool
    embedding: NotRequired[bool]
    embedding_source: NotRequired[str]
    embedding_error: NotRequired[str]


class QueueStatsResponse(TypedDict):
    queued: int
    completed: int
    failed: int
    pending: int
    processing: int
    retrying: NotRequired[int]
    dead_lettered: NotRequired[int]
    leased_processing: NotRequired[int]
    stale_processing: NotRequired[int]


class WorkerStatsResponse(TypedDict):
    online: bool
    heartbeat_at: str | None
    heartbeat_age_seconds: int | None


class DocumentStats(TypedDict):
    total: int
    ready: int
    pending: int
    processing: int
    failed: int
    total_chunks: int
    total_tokens: int
    total_size_bytes: int


class PlatformStatsResponse(TypedDict):
    collections: int
    documents: DocumentStats
    webhooks: int
    queue: QueueStatsResponse
    workers: NotRequired[WorkerStatsResponse]
