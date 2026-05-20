from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from bigrag.services.vector_store.base import VectorStoreProvider


class VectorMigrationCreateRequest(BaseModel):
    collection: str = Field(min_length=1, max_length=128)
    target_provider: VectorStoreProvider


class VectorMigrationJobResponse(BaseModel):
    id: str
    collection_id: str | None
    collection_name: str
    source_provider: VectorStoreProvider
    target_provider: VectorStoreProvider
    status: str
    phase: str
    progress: float
    copied_points: int
    total_points: int | None
    details: dict
    error_message: str | None = None
    created_by: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class VectorMigrationJobListResponse(BaseModel):
    jobs: list[VectorMigrationJobResponse]
    total: int | None = None
    next_cursor: str | None = None
