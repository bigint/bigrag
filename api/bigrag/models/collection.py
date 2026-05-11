from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class CreateCollectionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    description: str = ""
    embedding_preset_id: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    dimension: int | None = None
    chunk_size: int = Field(default=512, ge=64, le=10000)
    chunk_overlap: int = Field(default=50, ge=0, le=5000)
    chunk_strategy: str = Field(
        default="paragraph",
        pattern=r"^(paragraph|recursive)$",
        description="Chunking algorithm: paragraph (default) or recursive.",
    )
    index_type: str = Field(
        default="HNSW",
        pattern=r"^HNSW$",
        description="Vector index preference. Qdrant uses HNSW for dense-vector search.",
    )
    tenant_field: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "Optional metadata field name to index for tenant-aware Qdrant "
            "payload filtering in multi-tenant deployments."
        ),
    )
    metadata_schema: dict | None = Field(
        default=None,
        description=(
            "Optional JSON Schema (draft 2020-12 subset) — uploads with "
            "a metadata dict that fails validation are rejected before "
            "ingestion."
        ),
    )
    metadata: dict = {}
    reranking_enabled: bool = False
    reranking_model: str = "rerank-v3.5"
    reranking_api_key: str | None = None
    default_top_k: int = Field(default=10, ge=1, le=1000)
    default_min_score: float | None = None
    default_search_mode: str = Field(default="semantic", pattern=r"^(semantic|keyword|hybrid)$")

    @model_validator(mode="after")
    def validate_overlap_less_than_size(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return self


class UpdateCollectionRequest(BaseModel):
    description: str | None = None
    metadata: dict | None = None
    embedding_api_key: str | None = None
    reranking_enabled: bool | None = None
    reranking_model: str | None = None
    reranking_api_key: str | None = None
    default_top_k: int | None = Field(default=None, ge=1, le=1000)
    default_min_score: float | None = None
    default_search_mode: str | None = Field(default=None, pattern=r"^(semantic|keyword|hybrid)$")
    chunk_strategy: str | None = Field(default=None, pattern=r"^(paragraph|recursive)$")
    metadata_schema: dict | None = None


class CollectionResponse(BaseModel):
    id: str
    name: str
    description: str
    embedding_provider: str
    embedding_model: str
    dimension: int
    chunk_size: int
    chunk_overlap: int
    chunk_strategy: str = "paragraph"
    index_type: str = "HNSW"
    tenant_field: str | None = None
    has_metadata_schema: bool = False
    document_count: int
    has_api_key: bool = False
    embedding_preset_id: str | None = None
    reranking_enabled: bool = False
    reranking_model: str = "rerank-v3.5"
    has_reranking_api_key: bool = False
    default_top_k: int = 10
    default_min_score: float | None = None
    default_search_mode: str = "semantic"
    metadata: dict
    created_at: datetime
    updated_at: datetime


class CollectionListResponse(BaseModel):
    collections: list[CollectionResponse]
    total: int


class CollectionStatsResponse(BaseModel):
    collection: str
    document_count: int
    total_chunks: int
    total_tokens: int
    total_size_bytes: int
    status_counts: dict[str, int]
