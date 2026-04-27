"""Document types."""

from __future__ import annotations

from bigrag.types._compat import Any, TypedDict


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
    content_hash: str | None
    deduped: bool
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
