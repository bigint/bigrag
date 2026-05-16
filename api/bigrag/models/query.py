from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str
    top_k: int | None = Field(default=None, ge=1, le=1000)
    filters: dict | None = None
    min_score: float | None = None
    search_mode: str | None = Field(default=None, pattern=r"^(semantic|keyword|hybrid)$")
    rerank: bool | None = None


class VectorEntry(BaseModel):
    id: str
    embedding: list[float]
    text: str = ""
    metadata: dict = {}


class VectorUpsertRequest(BaseModel):
    vectors: list[VectorEntry]


class VectorDeleteRequest(BaseModel):
    ids: list[str]


class VectorUpsertResponse(BaseModel):
    status: str = "ok"
    upserted: int


class VectorDeleteResponse(BaseModel):
    status: str = "ok"
    deleted: int


class QueryResult(BaseModel):
    id: str
    text: str
    score: float
    document_id: str | None = None
    document_filename: str | None = None
    chunk_index: int | None = None
    page_no: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    metadata: dict = {}


class QueryTimings(BaseModel):
    embed_ms: float = 0.0
    search_ms: float = 0.0
    rerank_ms: float = 0.0
    cache_ms: float = 0.0
    total_ms: float = 0.0
    cache_hit: bool = False


class QueryResponse(BaseModel):
    results: list[QueryResult]
    query: str
    collection: str
    total: int
    timings: QueryTimings | None = None


class MultiQueryRequest(BaseModel):
    query: str
    collections: list[str] = Field(min_length=1, max_length=20)
    top_k: int = Field(default=10, ge=1, le=1000)
    filters: dict | None = None
    min_score: float | None = None
    search_mode: str = Field(default="semantic", pattern=r"^(semantic|keyword|hybrid)$")
    rerank: bool | None = None


class MultiQueryResult(BaseModel):
    id: str
    text: str
    score: float
    document_id: str | None = None
    document_filename: str | None = None
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


class EmbeddingModelListResponse(BaseModel):
    models: list[EmbeddingModelInfo]


class AnalyticsResponse(BaseModel):
    collection: str
    period_24h: dict
    period_7d: dict
    period_30d: dict
    top_queries: list[dict]
