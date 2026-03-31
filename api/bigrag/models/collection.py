from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class CreateCollectionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    description: str = ""
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    dimension: int | None = None
    chunk_size: int = Field(default=512, ge=64, le=10000)
    chunk_overlap: int = Field(default=50, ge=0, le=5000)
    metadata: dict = {}

    @model_validator(mode="after")
    def validate_overlap_less_than_size(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return self


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
    has_api_key: bool = False
    metadata: dict
    created_at: datetime
    updated_at: datetime


class CollectionListResponse(BaseModel):
    collections: list[CollectionResponse]
