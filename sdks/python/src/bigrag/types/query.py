"""Query types."""

from __future__ import annotations

from bigrag.types._compat import Any, NotRequired, TypedDict


class QueryBody(TypedDict):
    query: str
    top_k: NotRequired[int]
    filters: NotRequired[dict[str, Any]]
    min_score: NotRequired[float]
    search_mode: NotRequired[str]
    rerank: NotRequired[bool]
    diversity: NotRequired[float]
    hybrid_strategy: NotRequired[str]
    hyde: NotRequired[bool]
    facets: NotRequired[list[str]]
    use_semantic_cache: NotRequired[bool]


class QueryResult(TypedDict):
    id: str
    text: str
    score: float
    document_id: str | None
    chunk_index: int | None
    page_no: int | None
    char_start: int | None
    char_end: int | None
    metadata: dict[str, Any]


class QueryTimings(TypedDict):
    embed_ms: float
    search_ms: float
    rerank_ms: float
    hyde_ms: float
    mmr_ms: float
    total_ms: float


class QueryResponse(TypedDict):
    results: list[QueryResult]
    query: str
    collection: str
    total: int
    timings: NotRequired[QueryTimings | None]
    facets: NotRequired[dict[str, dict[str, int]] | None]
    cached: NotRequired[bool]


class MultiQueryBody(TypedDict):
    query: str
    collections: list[str]
    top_k: NotRequired[int]
    filters: NotRequired[dict[str, Any]]
    min_score: NotRequired[float]
    search_mode: NotRequired[str]
    rerank: NotRequired[bool]


class MultiQueryResult(TypedDict):
    id: str
    text: str
    score: float
    document_id: str | None
    chunk_index: int | None
    collection: str
    metadata: dict[str, Any]


class MultiQueryResponse(TypedDict):
    results: list[MultiQueryResult]
    query: str
    collections: list[str]
    total: int


class BatchQueryItem(TypedDict):
    collection: str
    query: str
    top_k: NotRequired[int]
    filters: NotRequired[dict[str, Any]]
    min_score: NotRequired[float]
    search_mode: NotRequired[str]
    rerank: NotRequired[bool]


class BatchQueryBody(TypedDict):
    queries: list[BatchQueryItem]


class BatchQueryResultItem(TypedDict):
    results: list[QueryResult]
    query: str
    collection: str
    total: int


class BatchQueryResponse(TypedDict):
    results: list[BatchQueryResultItem]
