from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

from .documents import MultimodalElementRef

SearchMode = Literal["semantic", "keyword", "hybrid"]


class QueryBody(TypedDict):
    query: str
    top_k: NotRequired[int]
    filters: NotRequired[dict[str, Any]]
    min_score: NotRequired[float]
    search_mode: NotRequired[SearchMode]
    rerank: NotRequired[bool]
    multimodal: NotRequired[bool]


class QueryResult(TypedDict):
    id: str
    text: str
    score: float
    document_id: str | None
    document_filename: str | None
    chunk_index: int | None
    page_no: int | None
    char_start: int | None
    char_end: int | None
    multimodal_elements: list[MultimodalElementRef]
    metadata: dict[str, Any]


class QueryTimings(TypedDict):
    embed_ms: float
    search_ms: float
    rerank_ms: float
    cache_ms: float
    total_ms: float
    cache_hit: bool


class QueryResponse(TypedDict):
    results: list[QueryResult]
    query: str
    collection: str
    total: int
    timings: NotRequired[QueryTimings | None]


class MultiQueryBody(TypedDict):
    query: str
    collections: list[str]
    top_k: NotRequired[int]
    filters: NotRequired[dict[str, Any]]
    min_score: NotRequired[float]
    search_mode: NotRequired[SearchMode]
    rerank: NotRequired[bool]
    multimodal: NotRequired[bool]


class MultiQueryResult(TypedDict):
    id: str
    text: str
    score: float
    document_id: str | None
    document_filename: str | None
    chunk_index: int | None
    collection: str
    multimodal_elements: list[MultimodalElementRef]
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
    search_mode: NotRequired[SearchMode]
    rerank: NotRequired[bool]
    multimodal: NotRequired[bool]


class BatchQueryBody(TypedDict):
    queries: list[BatchQueryItem]


class BatchQueryResultItem(TypedDict):
    results: list[QueryResult]
    query: str
    collection: str
    total: int


class BatchQueryResponse(TypedDict):
    results: list[BatchQueryResultItem]
