from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class VectorEntry(TypedDict):
    id: str
    embedding: list[float]
    text: NotRequired[str]
    metadata: NotRequired[dict[str, Any]]


class UpsertResponse(TypedDict):
    status: str
    upserted: int


class DeleteResponse(TypedDict):
    status: str
    deleted: int
