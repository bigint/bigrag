"""Type definitions for the bigRAG Python SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Collection:
    id: str
    name: str
    description: str
    embedding_provider: str
    embedding_model: str
    dimension: int
    chunk_size: int
    chunk_overlap: int
    document_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class CollectionListResponse:
    collections: list[Collection]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CollectionListResponse:
        return cls(
            collections=[Collection(**c) for c in data.get("collections", [])]
        )


@dataclass
class Document:
    id: str
    collection_id: str
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    status: str
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class DocumentListResponse:
    documents: list[Document]
    total: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentListResponse:
        return cls(
            documents=[Document(**d) for d in data.get("documents", [])],
            total=data.get("total", 0),
        )


@dataclass
class QueryResult:
    id: str
    text: str
    score: float
    document_id: str | None = None
    chunk_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryResponse:
    results: list[QueryResult]
    query: str
    collection: str
    total: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueryResponse:
        return cls(
            results=[QueryResult(**r) for r in data.get("results", [])],
            query=data.get("query", ""),
            collection=data.get("collection", ""),
            total=data.get("total", 0),
        )
