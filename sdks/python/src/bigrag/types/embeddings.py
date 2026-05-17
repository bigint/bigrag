from __future__ import annotations

from typing import TypedDict


class EmbeddingModelInfo(TypedDict):
    provider: str
    model: str
    dimension: int
    description: str


class EmbeddingModelListResponse(TypedDict):
    models: list[EmbeddingModelInfo]
