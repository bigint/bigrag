from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from bigrag._core import BigRAGCore
from bigrag._files import FileInput
from bigrag.resources import (
    AdminResource,
    AuthResource,
    ChatResource,
    CollectionsResource,
    ConnectorsResource,
    DocumentsResource,
    EvaluationsResource,
    QueryResource,
    VectorsResource,
    WebhooksResource,
)
from bigrag.types.analytics import AnalyticsResponse
from bigrag.types.chat import (
    ChatBody,
    ChatCreateResponse,
    ChatStreamEvent,
)
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
    DocumentElementListResponse,
    DocumentListResponse,
    UploadSession,
    UploadSessionFileResponse,
)
from bigrag.types.embeddings import EmbeddingModelListResponse
from bigrag.types.query import (
    QueryBody,
    QueryResponse,
)
from bigrag.types.sse import ProgressEvent
from bigrag.types.usage import UsageResponse


class BigRAG(BigRAGCore):
    collections: CollectionsResource
    connectors: ConnectorsResource
    documents: DocumentsResource
    queries: QueryResource
    vectors: VectorsResource
    webhooks: WebhooksResource
    chat: ChatResource
    auth: AuthResource
    admin: AdminResource
    evaluations: EvaluationsResource

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.collections = CollectionsResource(self)
        self.connectors = ConnectorsResource(self)
        self.documents = DocumentsResource(self)
        self.queries = QueryResource(self)
        self.vectors = VectorsResource(self)
        self.webhooks = WebhooksResource(self)
        self.chat = ChatResource(self)
        self.auth = AuthResource(self)
        self.admin = AdminResource(self)
        self.evaluations = EvaluationsResource(self)

    async def health(self) -> HealthResponse:
        return await self._request("GET", "/health")

    async def readiness(self) -> ReadinessResponse:
        return await self._request("GET", "/health/ready")

    async def get_stats(self) -> PlatformStatsResponse:
        return await self._request("GET", "/v1/stats")

    async def list_embedding_models(self) -> EmbeddingModelListResponse:
        return await self._request("GET", "/v1/embeddings/models")

    async def get_usage(self, *, window_days: int | None = None) -> UsageResponse:
        params: dict[str, str] = {}
        if window_days is not None:
            params["window_days"] = str(window_days)
        return await self._request("GET", "/v1/usage", params=params)

    async def chat_create(self, body: ChatBody) -> ChatCreateResponse:
        return await self.chat.create(body)

    async def chat_stream(
        self, body: ChatBody
    ) -> AsyncGenerator[ChatStreamEvent, None]:
        async for event in self.chat.stream(body):
            yield event

    def collection(self, name: str) -> CollectionClient:
        return CollectionClient(self, name)


class CollectionClient:
    def __init__(self, client: BigRAG, name: str) -> None:
        self._client = client
        self._name = name

    async def upload(
        self, file: FileInput, *, metadata: dict[str, Any] | None = None
    ) -> Document:
        return await self._client.documents.upload(self._name, file, metadata=metadata)

    async def list_documents(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> DocumentListResponse:
        return await self._client.documents.list(
            self._name, status=status, limit=limit, offset=offset
        )

    async def get_document(self, document_id: str) -> Document:
        return await self._client.documents.get(self._name, document_id)

    async def delete_document(self, document_id: str) -> StatusResponse:
        return await self._client.documents.delete(self._name, document_id)

    async def batch_upload(
        self, files: list[FileInput], *, metadata: dict[str, Any] | None = None
    ) -> DocumentListResponse:
        return await self._client.documents.batch_upload(
            self._name, files, metadata=metadata
        )

    async def create_upload_session(
        self,
        *,
        total_files: int,
        total_bytes: int,
        metadata: dict[str, Any] | None = None,
    ) -> UploadSession:
        return await self._client.documents.create_upload_session(
            self._name,
            total_files=total_files,
            total_bytes=total_bytes,
            metadata=metadata,
        )

    async def get_upload_session(self, session_id: str) -> UploadSession:
        return await self._client.documents.get_upload_session(self._name, session_id)

    async def upload_session_file(
        self,
        session_id: str,
        file: FileInput,
        *,
        client_item_id: str | None = None,
        filename: str | None = None,
    ) -> UploadSessionFileResponse:
        return await self._client.documents.upload_session_file(
            self._name,
            session_id,
            file,
            client_item_id=client_item_id,
            filename=filename,
        )

    async def complete_upload_session(self, session_id: str) -> UploadSession:
        return await self._client.documents.complete_upload_session(
            self._name, session_id
        )

    async def cancel_upload_session(self, session_id: str) -> StatusResponse:
        return await self._client.documents.cancel_upload_session(
            self._name, session_id
        )

    async def batch_get_status(self, document_ids: list[str]) -> BatchStatusResponse:
        return await self._client.documents.batch_get_status(self._name, document_ids)

    async def batch_get_documents(
        self, document_ids: list[str]
    ) -> BatchGetDocumentsResponse:
        return await self._client.documents.batch_get(self._name, document_ids)

    async def stats(self) -> CollectionStatsResponse:
        return await self._client.collections.stats(self._name)

    async def reembed(self) -> StatusResponse:
        return await self._client.collections.reembed(self._name)

    async def batch_delete(
        self, document_ids: list[str]
    ) -> BatchDeleteDocumentsResponse:
        return await self._client.documents.batch_delete(self._name, document_ids)

    async def reprocess_document(self, document_id: str) -> StatusResponse:
        return await self._client.documents.reprocess(self._name, document_id)

    async def get_document_chunks(
        self,
        document_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> DocumentChunkListResponse:
        return await self._client.documents.get_chunks(
            self._name, document_id, limit=limit, offset=offset
        )

    async def get_document_elements(
        self,
        document_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> DocumentElementListResponse:
        return await self._client.documents.get_elements(
            self._name, document_id, limit=limit, offset=offset
        )

    async def query(self, body: QueryBody) -> QueryResponse:
        return await self._client.queries.query(self._name, body)

    async def analytics(self) -> AnalyticsResponse:
        return await self._client.collections.analytics(self._name)

    async def stream_events(self) -> AsyncGenerator[ProgressEvent, None]:
        async for event in self._client.collections.stream_events(self._name):
            yield event
