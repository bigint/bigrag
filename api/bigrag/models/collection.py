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
    tenant_field: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "Optional metadata field name to index for tenant-aware "
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
    multimodal_enabled: bool = False
    multimodal_enrichment_enabled: bool = False
    default_top_k: int = Field(default=10, ge=1, le=200)
    default_min_score: float | None = None
    default_search_mode: str = Field(default="semantic", pattern=r"^(semantic|keyword|hybrid)$")

    @model_validator(mode="after")
    def validate_overlap_less_than_size(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        if self.multimodal_enrichment_enabled and not self.multimodal_enabled:
            raise ValueError("multimodal_enrichment_enabled requires multimodal_enabled")
        return self


class UpdateCollectionRequest(BaseModel):
    description: str | None = None
    metadata: dict | None = None
    embedding_api_key: str | None = None
    reranking_enabled: bool | None = None
    reranking_model: str | None = None
    reranking_api_key: str | None = None
    multimodal_enabled: bool | None = None
    multimodal_enrichment_enabled: bool | None = None
    default_top_k: int | None = Field(default=None, ge=1, le=200)
    default_min_score: float | None = None
    default_search_mode: str | None = Field(default=None, pattern=r"^(semantic|keyword|hybrid)$")
    chunk_strategy: str | None = Field(default=None, pattern=r"^(paragraph|recursive)$")
    metadata_schema: dict | None = None

    @model_validator(mode="after")
    def validate_multimodal_enrichment(self):
        if self.multimodal_enabled is False and self.multimodal_enrichment_enabled is True:
            raise ValueError("multimodal_enrichment_enabled requires multimodal_enabled")
        return self


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
    tenant_field: str | None = None
    has_metadata_schema: bool = False
    document_count: int
    has_api_key: bool = False
    embedding_preset_id: str | None = None
    reranking_enabled: bool = False
    reranking_model: str = "rerank-v3.5"
    has_reranking_api_key: bool = False
    multimodal_enabled: bool = False
    multimodal_enrichment_enabled: bool = False
    default_top_k: int = 10
    default_min_score: float | None = None
    default_search_mode: str = "semantic"
    metadata: dict
    created_at: datetime
    updated_at: datetime


class CollectionListResponse(BaseModel):
    collections: list[CollectionResponse]
    total: int | None = None
    next_cursor: str | None = None


class CollectionStatsResponse(BaseModel):
    collection: str
    document_count: int
    total_chunks: int
    total_tokens: int
    total_size_bytes: int
    status_counts: dict[str, int]
