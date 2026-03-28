"""Type definitions for the bigRAG Python SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class Document:
    """A document to upsert into a namespace."""

    id: int | str
    vector: list[float] | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {"id": self.id}
        if self.vector is not None:
            row["vector"] = self.vector
        row.update(self.attributes)
        return row


@dataclass
class QueryRow:
    """A single row returned from a query."""

    id: int | str
    dist: float | None = None
    vector: list[float] | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueryRow:
        return cls(
            id=data["id"],
            dist=data.get("dist"),
            vector=data.get("vector"),
            attributes={
                k: v
                for k, v in data.items()
                if k not in ("id", "dist", "vector")
            },
        )


@dataclass
class QueryResponse:
    """Response from a query operation."""

    rows: List[QueryRow]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QueryResponse:
        return cls(
            rows=[QueryRow.from_dict(r) for r in data.get("rows", [])],
        )


@dataclass
class WriteResponse:
    """Response from a write operation (upsert, delete, patch)."""

    status: str
    rows_affected: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WriteResponse:
        return cls(
            status=data.get("status", "ok"),
            rows_affected=data.get("rows_affected", 0),
        )


@dataclass
class NamespaceSummary:
    """Summary of a namespace from the list endpoint."""

    id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NamespaceSummary:
        return cls(id=data["id"])


@dataclass
class NamespaceListResponse:
    """Response from listing namespaces."""

    namespaces: List[NamespaceSummary]
    next_cursor: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NamespaceListResponse:
        return cls(
            namespaces=[
                NamespaceSummary.from_dict(ns)
                for ns in data.get("namespaces", [])
            ],
            next_cursor=data.get("next_cursor"),
        )


@dataclass
class NamespaceMetadata:
    """Metadata about a namespace."""

    schema: dict[str, Any] = field(default_factory=dict)
    approx_row_count: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NamespaceMetadata:
        return cls(
            schema=data.get("schema", {}),
            approx_row_count=data.get("approx_row_count", 0),
            extra={
                k: v
                for k, v in data.items()
                if k not in ("schema", "approx_row_count")
            },
        )
