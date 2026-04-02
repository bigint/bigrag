from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


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


class DocumentChunkResponse(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    text: str
    metadata: dict


class UrlIngestionRequest(BaseModel):
    url: str
    crawl_depth: int = Field(default=0, ge=0, le=3)
    max_pages: int = Field(default=1, ge=1, le=100)
    metadata: dict = {}
