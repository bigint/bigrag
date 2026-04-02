from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class CreateCollectionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    description: str = ""
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None
    dimension: int | None = None
    chunk_size: int = Field(default=512, ge=64, le=10000)
    chunk_overlap: int = Field(default=50, ge=0, le=5000)
    metadata: dict = {}
    reranking_enabled: bool = False
    reranking_model: str = "rerank-v3.5"
    reranking_api_key: str | None = None

    @model_validator(mode="after")
    def validate_overlap_less_than_size(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return self


class UpdateCollectionRequest(BaseModel):
    description: str | None = None
    metadata: dict | None = None
    reranking_enabled: bool | None = None
    reranking_model: str | None = None
    reranking_api_key: str | None = None


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
    reranking_enabled: bool = False
    reranking_model: str = "rerank-v3.5"
    has_reranking_api_key: bool = False
    metadata: dict
    created_at: datetime
    updated_at: datetime


class CollectionListResponse(BaseModel):
    collections: list[CollectionResponse]
