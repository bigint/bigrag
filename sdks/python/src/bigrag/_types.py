"""Type definitions for the bigRAG Python SDK.

All request/response shapes are expressed as :class:`~typing.TypedDict` classes
so that type-checkers can validate usage without any runtime overhead.
"""

from __future__ import annotations

import sys
from typing import Any

if sys.version_info >= (3, 11):
    from typing import NotRequired, TypedDict
else:
    from typing_extensions import NotRequired, TypedDict

# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------


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
    milvus: bool
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


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


class Collection(TypedDict):
    id: str
    name: str
    description: str
    embedding_provider: str
    embedding_model: str
    dimension: int
    chunk_size: int
    chunk_overlap: int
    document_count: int
    has_api_key: bool
    reranking_enabled: bool
    reranking_model: str
    has_reranking_api_key: bool
    default_top_k: int
    default_min_score: float | None
    default_search_mode: str
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


class CollectionListResponse(TypedDict):
    collections: list[Collection]
    total: int


class CollectionStatsResponse(TypedDict):
    collection: str
    document_count: int
    total_chunks: int
    total_tokens: int
    total_size_bytes: int
    status_counts: dict[str, int]


class CreateCollectionBody(TypedDict):
    name: str
    description: NotRequired[str]
    embedding_provider: NotRequired[str]
    embedding_model: NotRequired[str]
    embedding_api_key: NotRequired[str]
    dimension: NotRequired[int]
    chunk_size: NotRequired[int]
    chunk_overlap: NotRequired[int]
    reranking_enabled: NotRequired[bool]
    reranking_model: NotRequired[str]
    reranking_api_key: NotRequired[str]
    default_top_k: NotRequired[int]
    default_min_score: NotRequired[float]
    default_search_mode: NotRequired[str]


class UpdateCollectionBody(TypedDict, total=False):
    description: str
    metadata: dict[str, Any]
    reranking_enabled: bool
    reranking_model: str
    reranking_api_key: str
    default_top_k: int
    default_min_score: float
    default_search_mode: str


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class Document(TypedDict):
    id: str
    collection_id: str
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    status: str
    error_message: str | None
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


class DocumentListResponse(TypedDict):
    documents: list[Document]
    total: int


class DocumentChunk(TypedDict):
    id: str
    document_id: str
    chunk_index: int
    text: str
    metadata: dict[str, Any]


class DocumentChunkListResponse(TypedDict):
    chunks: list[DocumentChunk]
    total: int


class DocumentStatus(TypedDict):
    id: str
    status: str
    error_message: str | None
    chunk_count: int


class BatchStatusResponse(TypedDict):
    documents: list[DocumentStatus]
    total: int


class BatchGetDocumentsResponse(TypedDict):
    documents: list[Document]
    total: int


class BatchDeleteError(TypedDict):
    document_id: str
    error: str


class BatchDeleteDocumentsResponse(TypedDict):
    status: str
    deleted: int
    errors: list[BatchDeleteError]


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


class QueryBody(TypedDict):
    query: str
    top_k: NotRequired[int]
    filters: NotRequired[dict[str, Any]]
    min_score: NotRequired[float]
    search_mode: NotRequired[str]
    rerank: NotRequired[bool]


class QueryResult(TypedDict):
    id: str
    text: str
    score: float
    document_id: str | None
    chunk_index: int | None
    metadata: dict[str, Any]


class QueryResponse(TypedDict):
    results: list[QueryResult]
    query: str
    collection: str
    total: int


class MultiQueryBody(TypedDict):
    query: str
    collections: list[str]
    top_k: NotRequired[int]
    filters: NotRequired[dict[str, Any]]
    min_score: NotRequired[float]
    search_mode: NotRequired[str]


class MultiQueryResult(TypedDict):
    id: str
    text: str
    score: float
    document_id: str | None
    chunk_index: int | None
    collection: str
    metadata: dict[str, Any]


class MultiQueryResponse(TypedDict):
    results: list[MultiQueryResult]
    query: str
    collections: list[str]
    total: int


class BatchQueryItem(TypedDict):
    collection: str
    query: str
    top_k: NotRequired[int]
    filters: NotRequired[dict[str, Any]]
    min_score: NotRequired[float]
    search_mode: NotRequired[str]
    rerank: NotRequired[bool]


class BatchQueryBody(TypedDict):
    queries: list[BatchQueryItem]


class BatchQueryResultItem(TypedDict):
    results: list[QueryResult]
    query: str
    collection: str
    total: int


class BatchQueryResponse(TypedDict):
    results: list[BatchQueryResultItem]


# ---------------------------------------------------------------------------
# Vectors
# ---------------------------------------------------------------------------


class VectorEntry(TypedDict):
    id: str
    embedding: list[float]
    text: NotRequired[str]
    metadata: NotRequired[dict[str, Any]]


class UpsertResponse(TypedDict):
    status: str
    upserted: int


class DeleteResponse(TypedDict):
    status: str
    deleted: int


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


class Webhook(TypedDict):
    id: str
    url: str
    events: list[str]
    collections: list[str] | None
    description: str
    active: bool
    created_by: str | None
    created_at: str
    updated_at: str


class CreateWebhookBody(TypedDict):
    url: str
    events: list[str]
    collections: NotRequired[list[str]]
    description: NotRequired[str]


class CreateWebhookResponse(TypedDict):
    id: str
    url: str
    events: list[str]
    collections: list[str] | None
    description: str
    active: bool
    created_by: str | None
    created_at: str
    updated_at: str
    secret: str


class UpdateWebhookBody(TypedDict, total=False):
    url: str
    events: list[str]
    collections: list[str] | None
    description: str
    active: bool


class WebhookListResponse(TypedDict):
    webhooks: list[Webhook]


class WebhookDelivery(TypedDict):
    id: str
    webhook_id: str
    event: str
    payload: dict[str, Any]
    status: str
    attempts: int
    last_status_code: int | None
    last_error: str | None
    created_at: str
    completed_at: str | None


class WebhookDeliveryListResponse(TypedDict):
    deliveries: list[WebhookDelivery]
    total: int


class WebhookTestResponse(TypedDict):
    status: str
    status_code: int | None
    error: str | None


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class PeriodStats(TypedDict):
    query_count: int
    avg_latency_ms: float
    avg_score: float
    avg_result_count: float


class TopQuery(TypedDict):
    query: str
    count: int


class AnalyticsResponse(TypedDict):
    collection: str
    period_24h: PeriodStats
    period_7d: PeriodStats
    period_30d: PeriodStats
    top_queries: list[TopQuery]


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


class EmbeddingModelInfo(TypedDict):
    provider: str
    model: str
    dimension: int
    description: str


class EmbeddingModelListResponse(TypedDict):
    models: list[EmbeddingModelInfo]


# ---------------------------------------------------------------------------
# Ingestion Sources
# ---------------------------------------------------------------------------


class S3IngestBody(TypedDict):
    bucket: str
    prefix: NotRequired[str]
    region: NotRequired[str]
    endpoint_url: NotRequired[str]
    access_key: NotRequired[str]
    secret_key: NotRequired[str]
    no_sign_request: NotRequired[bool]
    metadata: NotRequired[dict[str, Any]]


class S3IngestResponse(TypedDict):
    status: str
    documents: list[Document]
    total: int
    skipped: list[str]


# ---------------------------------------------------------------------------
# SSE
# ---------------------------------------------------------------------------


class ProgressEvent(TypedDict):
    step: str
    message: str
    progress: float
    status: NotRequired[str]
    detail: NotRequired[dict[str, Any]]
