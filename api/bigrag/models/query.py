from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str
    top_k: int | None = Field(default=None, ge=1, le=1000)
    filters: dict | None = None
    min_score: float | None = None
    search_mode: str | None = Field(default=None, pattern=r"^(semantic|keyword|hybrid)$")
    rerank: bool | None = None  # Override collection's reranking_enabled
    # Retrieval-quality knobs
    diversity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "0 = pure relevance (default). 1 = maximum novelty. Applied as "
            "MMR over the top_k*3 candidates before trimming to top_k."
        ),
    )
    hybrid_strategy: str | None = Field(
        default=None,
        pattern=r"^(rrf|weighted|normalized)$",
        description="Fusion strategy when search_mode=hybrid.",
    )
    hyde: bool | None = Field(
        default=None,
        description=(
            "Generate a hypothetical answer with an LLM, embed THAT, and "
            "retrieve against it. Boosts recall on underspecified queries."
        ),
    )
    facets: list[str] | None = Field(
        default=None,
        max_length=10,
        description="Metadata fields to aggregate counts over in the response.",
    )


class VectorEntry(BaseModel):
    id: str
    embedding: list[float]
    text: str = ""
    metadata: dict = {}


class VectorUpsertRequest(BaseModel):
    vectors: list[VectorEntry]


class VectorDeleteRequest(BaseModel):
    ids: list[str]


class QueryResult(BaseModel):
    id: str
    text: str
    score: float
    document_id: str | None = None
    chunk_index: int | None = None
    # Citation provenance (populated when Docling surfaces them during
    # ingestion). Useful for inline LLM citations.
    page_no: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    metadata: dict = {}


class QueryTimings(BaseModel):
    """Per-phase latency breakdown so clients / Studio can show a debugger."""

    embed_ms: float = 0.0
    search_ms: float = 0.0
    rerank_ms: float = 0.0
    hyde_ms: float = 0.0
    mmr_ms: float = 0.0
    total_ms: float = 0.0


class QueryResponse(BaseModel):
    results: list[QueryResult]
    query: str
    collection: str
    total: int
    timings: QueryTimings | None = None
    facets: dict[str, dict[str, int]] | None = None
    cached: bool = False  # set true when the semantic cache served this


class MultiQueryRequest(BaseModel):
    query: str
    collections: list[str] = Field(min_length=1, max_length=20)
    top_k: int = Field(default=10, ge=1, le=1000)
    filters: dict | None = None
    min_score: float | None = None
    search_mode: str = Field(default="semantic", pattern=r"^(semantic|keyword|hybrid)$")
    rerank: bool | None = None  # Override collection's reranking_enabled


class MultiQueryResult(BaseModel):
    id: str
    text: str
    score: float
    document_id: str | None = None
    chunk_index: int | None = None
    collection: str = ""
    metadata: dict = {}


class MultiQueryResponse(BaseModel):
    results: list[MultiQueryResult]
    query: str
    collections: list[str]
    total: int


class BatchQueryItem(BaseModel):
    collection: str
    query: str
    top_k: int = Field(default=10, ge=1, le=1000)
    filters: dict | None = None
    min_score: float | None = None
    search_mode: str = Field(default="semantic", pattern=r"^(semantic|keyword|hybrid)$")
    rerank: bool | None = None


class BatchQueryRequest(BaseModel):
    queries: list[BatchQueryItem] = Field(min_length=1, max_length=20)


class BatchQueryResultItem(BaseModel):
    results: list[QueryResult]
    query: str
    collection: str
    total: int


class BatchQueryResponse(BaseModel):
    results: list[BatchQueryResultItem]


class EmbeddingModelInfo(BaseModel):
    provider: str
    model: str
    dimension: int
    description: str = ""


class AnalyticsResponse(BaseModel):
    collection: str
    period_24h: dict
    period_7d: dict
    period_30d: dict
    top_queries: list[dict]
