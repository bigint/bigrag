from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UploadSessionCreateRequest(BaseModel):
    total_files: int = Field(ge=1)
    total_bytes: int = Field(ge=0)
    metadata: dict = Field(default_factory=dict)


class UploadSessionItemResponse(BaseModel):
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
    created_at: datetime
    updated_at: datetime


class UploadSessionResponse(BaseModel):
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
    recent_items: list[UploadSessionItemResponse]
    metadata: dict
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class UploadSessionFileResponse(BaseModel):
    item: UploadSessionItemResponse
    session: UploadSessionResponse
