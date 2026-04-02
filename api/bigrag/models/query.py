from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=10, ge=1, le=1000)
    filters: dict | None = None
    min_score: float | None = None


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
    metadata: dict = {}


class QueryResponse(BaseModel):
    results: list[QueryResult]
    query: str
    collection: str
    total: int


class MultiQueryRequest(BaseModel):
    query: str
    collections: list[str] = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=1000)
    filters: dict | None = None
    min_score: float | None = None


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


class EmbeddingModelInfo(BaseModel):
    provider: str
    model: str
    dimension: int
    description: str = ""
