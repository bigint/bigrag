"""Common types shared across the SDK."""

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
    qdrant: bool
    redis: bool
    embedding: NotRequired[bool]
    embedding_error: NotRequired[str]


class QueueStatsResponse(TypedDict):
    queued: int
    completed: int
    failed: int
    pending: int
    processing: int


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
