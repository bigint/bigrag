"""High-level bigRAG client."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import quote

from bigrag._core import BigRAGCore
from bigrag._files import FileInput
from bigrag.resources import (
    AdminResource,
    AuthResource,
    CollectionsResource,
    DocumentsResource,
    EvaluationsResource,
    QueryResource,
    VectorsResource,
    WebhooksResource,
)
from bigrag.types.analytics import AnalyticsResponse
from bigrag.types.collections import CollectionStatsResponse
from bigrag.types.common import (
    HealthResponse,
    PlatformStatsResponse,
    ReadinessResponse,
    StatusResponse,
)
from bigrag.types.documents import (
    BatchDeleteDocumentsResponse,
    BatchGetDocumentsResponse,
    BatchStatusResponse,
    Document,
    DocumentChunkListResponse,
    DocumentListResponse,
)
from bigrag.types.embeddings import EmbeddingModelListResponse
from bigrag.types.query import (
    QueryBody,
    QueryResponse,
)
from bigrag.types.sse import ProgressEvent
from bigrag.types.usage import UsageResponse


class BigRAG(BigRAGCore):
    """Main bigRAG client.

    Exposes **resource namespaces** (``collections``, ``documents``,
    ``queries``, ``vectors``, ``webhooks``) following the Stripe SDK pattern.

    Platform-level endpoints (``health``, ``readiness``, ``get_stats``,
    ``list_embedding_models``) remain directly on this class.
    """

    collections: CollectionsResource
    documents: DocumentsResource
    queries: QueryResource
    vectors: VectorsResource
    webhooks: WebhooksResource
    auth: AuthResource
    admin: AdminResource
    evaluations: EvaluationsResource

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.collections = CollectionsResource(self)
        self.documents = DocumentsResource(self)
        self.queries = QueryResource(self)
        self.vectors = VectorsResource(self)
        self.webhooks = WebhooksResource(self)
        self.auth = AuthResource(self)
        self.admin = AdminResource(self)
        self.evaluations = EvaluationsResource(self)

    async def health(self) -> HealthResponse:
        """Check whether the API server is running."""
        return await self._request("GET", "/health")

    async def readiness(self) -> ReadinessResponse:
        """Check whether all backing services are reachable."""
        return await self._request("GET", "/health/ready")

    async def get_stats(self) -> PlatformStatsResponse:
        """Retrieve platform-wide statistics."""
        return await self._request("GET", "/v1/stats")

    async def list_embedding_models(self) -> EmbeddingModelListResponse:
        """List all available embedding models."""
        return await self._request("GET", "/v1/embeddings/models")

    async def get_analytics(self, collection: str) -> AnalyticsResponse:
        """Retrieve analytics for a specific collection."""
        return await self._request(
            "GET", f"/v1/collections/{quote(collection, safe='')}/analytics"
        )

    async def get_usage(self, *, window_days: int | None = None) -> UsageResponse:
        """Retrieve workspace usage analytics."""
        params: dict[str, str] = {}
        if window_days is not None:
            params["window_days"] = str(window_days)
        return await self._request("GET", "/v1/usage", params=params)

    def collection(self, name: str) -> CollectionClient:
        """Create a scoped client for a specific collection."""
        return CollectionClient(self, name)


class CollectionClient:
    """A convenience wrapper that scopes all operations to a single collection.

    Delegates to the resource namespaces on the parent :class:`BigRAG` client.
    """

    def __init__(self, client: BigRAG, name: str) -> None:
        self._client = client
        self._name = name

    async def upload(
        self, file: FileInput, *, metadata: dict[str, Any] | None = None
    ) -> Document:
        """Upload a document to this collection."""
        return await self._client.documents.upload(
            self._name, file, metadata=metadata
        )

    async def list_documents(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> DocumentListResponse:
        """List documents in this collection."""
        return await self._client.documents.list(
            self._name, status=status, limit=limit, offset=offset
        )

    async def get_document(self, document_id: str) -> Document:
        """Get a document by ID from this collection."""
        return await self._client.documents.get(self._name, document_id)

    async def delete_document(self, document_id: str) -> StatusResponse:
        """Delete a document by ID from this collection."""
        return await self._client.documents.delete(self._name, document_id)

    async def batch_upload(
        self, files: list[FileInput], *, metadata: dict[str, Any] | None = None
    ) -> DocumentListResponse:
        """Upload multiple documents to this collection."""
        return await self._client.documents.batch_upload(
            self._name, files, metadata=metadata
        )

    async def batch_get_status(self, document_ids: list[str]) -> BatchStatusResponse:
        """Get the processing status of multiple documents."""
        return await self._client.documents.batch_get_status(
            self._name, document_ids
        )

    async def batch_get_documents(
        self, document_ids: list[str]
    ) -> BatchGetDocumentsResponse:
        """Retrieve multiple documents by ID."""
        return await self._client.documents.batch_get(self._name, document_ids)

    async def stats(self) -> CollectionStatsResponse:
        """Get statistics for this collection."""
        return await self._client.collections.stats(self._name)

    async def reembed(self) -> StatusResponse:
        """Queue all ready/failed documents in this collection for re-embedding."""
        return await self._client.collections.reembed(self._name)

    async def batch_delete(
        self, document_ids: list[str]
    ) -> BatchDeleteDocumentsResponse:
        """Delete multiple documents from this collection."""
        return await self._client.documents.batch_delete(self._name, document_ids)

    async def reprocess_document(self, document_id: str) -> StatusResponse:
        """Trigger reprocessing of a document."""
        return await self._client.documents.reprocess(self._name, document_id)

    async def get_document_chunks(
        self,
        document_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> DocumentChunkListResponse:
        """Get all chunks for a document."""
        return await self._client.documents.get_chunks(
            self._name, document_id, limit=limit, offset=offset
        )

    async def query(self, body: QueryBody) -> QueryResponse:
        """Query this collection."""
        return await self._client.queries.query(self._name, body)

    async def analytics(self) -> AnalyticsResponse:
        """Get analytics for this collection."""
        return await self._client.get_analytics(self._name)

    async def stream_document_progress(
        self, document_id: str
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Stream real-time processing progress for a document."""
        async for event in self._client.documents.stream_progress(
            self._name, document_id
        ):
            yield event

    async def stream_batch_progress(
        self, document_ids: list[str]
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Stream aggregated progress for multiple documents."""
        async for event in self._client.documents.stream_batch_progress(
            self._name, document_ids
        ):
            yield event

    async def stream_events(self) -> AsyncGenerator[ProgressEvent, None]:
        """Stream real-time events for this collection via SSE."""
        async for event in self._client.collections.stream_events(self._name):
            yield event
