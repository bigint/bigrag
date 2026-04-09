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


class QueryResult(TypedDict):
    id: str
    text: str
    score: float
    document_id: str | None
    chunk_index: int | None
    metadata: dict[str, Any]


class QueryResponse(TypedDict):
    results: list[QueryResult]
    query: str
    collection: str
    total: int


class MultiQueryBody(TypedDict):
    query: str
    collections: list[str]
    top_k: NotRequired[int]
    filters: NotRequired[dict[str, Any]]
    min_score: NotRequired[float]
    search_mode: NotRequired[str]


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
