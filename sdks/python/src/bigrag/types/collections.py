from __future__ import annotations

from typing import Any, NotRequired, TypedDict

from .query import SearchMode


class Collection(TypedDict):
    id: str
    name: str
    description: str
    embedding_model: str
    dimension: int
    chunk_size: int
    chunk_overlap: int
    chunk_strategy: str
    tenant_field: str | None
    has_metadata_schema: bool
    document_count: int
    has_api_key: bool
    embedding_preset_id: str | None
    reranking_enabled: bool
    reranking_model: str
    has_reranking_api_key: bool
    multimodal_enabled: bool
    multimodal_enrichment_enabled: bool
    default_top_k: int
    default_min_score: float | None
    default_search_mode: SearchMode
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


class CollectionListResponse(TypedDict):
    collections: list[Collection]
    total: int | None


class CollectionStatsResponse(TypedDict):
    collection: str
    document_count: int
    total_chunks: int
    total_tokens: int
    total_size_bytes: int
    status_counts: dict[str, int]


class CollectionEventTokenResponse(TypedDict):
    token: str
    expires_in: int


class CreateCollectionBody(TypedDict):
    name: str
    description: NotRequired[str]
    embedding_preset_id: NotRequired[str]
    embedding_model: NotRequired[str]
    embedding_api_key: NotRequired[str]
    embedding_base_url: NotRequired[str]
    dimension: NotRequired[int]
    chunk_size: NotRequired[int]
    chunk_overlap: NotRequired[int]
    chunk_strategy: NotRequired[str]
    tenant_field: NotRequired[str]
    metadata_schema: NotRequired[dict[str, Any]]
    metadata: NotRequired[dict[str, Any]]
    reranking_enabled: NotRequired[bool]
    reranking_model: NotRequired[str]
    reranking_api_key: NotRequired[str]
    multimodal_enabled: NotRequired[bool]
    multimodal_enrichment_enabled: NotRequired[bool]
    default_top_k: NotRequired[int]
    default_min_score: NotRequired[float]
    default_search_mode: NotRequired[SearchMode]


class UpdateCollectionBody(TypedDict, total=False):
    description: str
    metadata: dict[str, Any]
    embedding_api_key: str | None
    reranking_enabled: bool
    reranking_model: str
    reranking_api_key: str | None
    multimodal_enabled: bool
    multimodal_enrichment_enabled: bool
    default_top_k: int
    default_min_score: float
    default_search_mode: SearchMode
    chunk_strategy: str
    metadata_schema: dict[str, Any]
