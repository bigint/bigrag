"""Embedding model types."""

from __future__ import annotations

from bigrag.types._compat import TypedDict


class EmbeddingModelInfo(TypedDict):
    provider: str
    model: str
    dimension: int
    description: str


class EmbeddingModelListResponse(TypedDict):
    models: list[EmbeddingModelInfo]
