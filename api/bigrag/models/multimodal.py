from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MultimodalElementRef(BaseModel):
    document_id: str | None = None
    element_index: int
    kind: str
    text: str = ""
    summary: str | None = None
    caption: str | None = None
    asset_path: str | None = None
    page_no: int | None = None
    bbox: dict | list | None = None
    metadata: dict = Field(default_factory=dict)


class DocumentElementResponse(BaseModel):
    id: str
    document_id: str
    collection_id: str
    element_index: int
    kind: str
    text: str
    summary: str | None = None
    caption: str | None = None
    asset_path: str | None = None
    page_no: int | None = None
    bbox: dict | list | None = None
    char_start: int | None = None
    char_end: int | None = None
    surrounding_context: str | None = None
    metadata: dict = Field(default_factory=dict)
    enrichment_status: str
    enrichment_error: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentElementListResponse(BaseModel):
    elements: list[DocumentElementResponse]
    total: int
