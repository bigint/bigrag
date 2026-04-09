from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    collection_id: str
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    status: str
    error_message: str | None = None
    metadata: dict
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class BatchStatusRequest(BaseModel):
    document_ids: list[str]


class DocumentStatusResponse(BaseModel):
    id: str
    status: str
    error_message: str | None = None
    chunk_count: int


class BatchStatusResponse(BaseModel):
    documents: list[DocumentStatusResponse]
    total: int


class BatchGetRequest(BaseModel):
    document_ids: list[str]


class BatchGetResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class BatchDeleteRequest(BaseModel):
    document_ids: list[str]


class BatchDeleteResponse(BaseModel):
    status: str
    deleted: int
    errors: list[dict] = []


class S3IngestRequest(BaseModel):
    bucket: str
    prefix: str = ""
    region: str = "us-east-1"
    endpoint_url: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    metadata: dict = {}


class S3IngestResponse(BaseModel):
    status: str
    documents: list[DocumentResponse]
    total: int
    skipped: list[str] = []
