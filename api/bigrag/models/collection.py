from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class CreateCollectionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    description: str = ""
    embedding_provider: str | None = None
    embedding_model: str | None = None
    dimension: int | None = None
    chunk_size: int = 512
    chunk_overlap: int = 50
    metadata: dict = {}


class UpdateCollectionRequest(BaseModel):
    description: str | None = None
    metadata: dict | None = None


class CollectionResponse(BaseModel):
    id: str
    name: str
    description: str
    embedding_provider: str
    embedding_model: str
    dimension: int
    chunk_size: int
    chunk_overlap: int
    document_count: int
    metadata: dict
    created_at: datetime
    updated_at: datetime


class CollectionListResponse(BaseModel):
    collections: list[CollectionResponse]
