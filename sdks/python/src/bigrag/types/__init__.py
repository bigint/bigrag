"""Type definitions for the bigRAG Python SDK.

All types are re-exported here for convenience.
"""

from bigrag.types.analytics import AnalyticsResponse, PeriodStats, TopQuery
from bigrag.types.collections import (
    Collection,
    CollectionListResponse,
    CollectionStatsResponse,
    CreateCollectionBody,
    UpdateCollectionBody,
)
from bigrag.types.common import (
    DocumentStats,
    HealthResponse,
    PlatformStatsResponse,
    QueueStatsResponse,
    ReadinessResponse,
    StatusResponse,
)
from bigrag.types.documents import (
    BatchDeleteDocumentsResponse,
    BatchDeleteError,
    BatchGetDocumentsResponse,
    BatchStatusResponse,
    Document,
    DocumentChunk,
    DocumentChunkListResponse,
    DocumentListResponse,
    DocumentStatus,
)
from bigrag.types.embeddings import EmbeddingModelInfo, EmbeddingModelListResponse
from bigrag.types.query import (
    BatchQueryBody,
    BatchQueryItem,
    BatchQueryResponse,
    BatchQueryResultItem,
    MultiQueryBody,
    MultiQueryResponse,
    MultiQueryResult,
    QueryBody,
    QueryResponse,
    QueryResult,
)
from bigrag.types.s3 import S3IngestBody, S3IngestResponse
from bigrag.types.sse import ProgressEvent
from bigrag.types.vectors import DeleteResponse, UpsertResponse, VectorEntry
from bigrag.types.webhooks import (
    CreateWebhookBody,
    CreateWebhookResponse,
    UpdateWebhookBody,
    Webhook,
    WebhookDelivery,
    WebhookDeliveryListResponse,
    WebhookListResponse,
    WebhookTestResponse,
)

__all__ = [
    # Common
    "StatusResponse",
    "HealthResponse",
    "ReadinessResponse",
    "QueueStatsResponse",
    "DocumentStats",
    "PlatformStatsResponse",
    # Collections
    "Collection",
    "CollectionListResponse",
    "CollectionStatsResponse",
    "CreateCollectionBody",
    "UpdateCollectionBody",
    # Documents
    "Document",
    "DocumentListResponse",
    "DocumentChunk",
    "DocumentChunkListResponse",
    "DocumentStatus",
    "BatchStatusResponse",
    "BatchGetDocumentsResponse",
    "BatchDeleteError",
    "BatchDeleteDocumentsResponse",
    # Query
    "QueryBody",
    "QueryResult",
    "QueryResponse",
    "MultiQueryBody",
    "MultiQueryResult",
    "MultiQueryResponse",
    "BatchQueryItem",
    "BatchQueryBody",
    "BatchQueryResultItem",
    "BatchQueryResponse",
    # Vectors
    "VectorEntry",
    "UpsertResponse",
    "DeleteResponse",
    # Webhooks
    "Webhook",
    "CreateWebhookBody",
    "CreateWebhookResponse",
    "UpdateWebhookBody",
    "WebhookListResponse",
    "WebhookDelivery",
    "WebhookDeliveryListResponse",
    "WebhookTestResponse",
    # Analytics
    "PeriodStats",
    "TopQuery",
    "AnalyticsResponse",
    # Embeddings
    "EmbeddingModelInfo",
    "EmbeddingModelListResponse",
    # S3
    "S3IngestBody",
    "S3IngestResponse",
    # SSE
    "ProgressEvent",
]
