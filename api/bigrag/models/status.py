from __future__ import annotations

from pydantic import BaseModel


class OverviewStatusResponse(BaseModel):
    platform: dict[str, object]
    readiness: dict[str, object]


class CollectionsStatusResponse(BaseModel):
    collections_total: int
    documents_total: int
    documents_ready: int
    documents_pending: int
    documents_processing: int
    documents_failed: int
    total_chunks: int
    total_tokens: int
    total_size_bytes: int
