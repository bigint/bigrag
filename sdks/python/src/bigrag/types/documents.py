from __future__ import annotations

from typing import Any, TypedDict


class DocumentProgress(TypedDict):
    document_id: str
    collection_name: str
    step: str
    status: str
    message: str
    progress: float
    detail: dict[str, Any]


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
    progress: DocumentProgress | None
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
    progress: DocumentProgress | None


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


class UploadSessionCreateRequest(TypedDict, total=False):
    total_files: int
    total_bytes: int
    metadata: dict[str, Any]


class UploadSessionItem(TypedDict):
    id: str
    client_item_id: str
    document_id: str | None
    filename: str
    file_type: str
    file_size: int
    content_hash: str | None
    status: str
    document_status: str | None
    error_message: str | None
    created_at: str
    updated_at: str


class UploadSession(TypedDict):
    id: str
    collection_id: str
    collection_name: str
    status: str
    total_files: int
    total_bytes: int
    uploaded_files: int
    queued_files: int
    processing_files: int
    completed_files: int
    failed_files: int
    canceled_files: int
    active_files: int
    recent_items: list[UploadSessionItem]
    metadata: dict[str, Any]
    created_at: str
    updated_at: str
    closed_at: str | None


class UploadSessionFileResponse(TypedDict):
    item: UploadSessionItem
    session: UploadSession
