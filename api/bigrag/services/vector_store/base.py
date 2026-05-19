from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Literal, Protocol

from bigrag.services._retrieval_filters import FilterExpression

VectorStoreProvider = Literal["qdrant", "turbopuffer"]

_POINT_NAMESPACE = uuid.UUID("1b04f7ca-0c3b-5d76-a5bb-6e4b4a40f61d")
_FIXED_PAYLOAD_FIELDS = {"id", "text", "document_id", "chunk_index", "embedding"}
DEFAULT_SEARCH_PAYLOAD_FIELDS: list[str] = [
    "id",
    "text",
    "document_id",
    "chunk_index",
    "page_no",
    "char_start",
    "char_end",
]


class VectorStoreFeatureError(RuntimeError):
    pass


class VectorStoreBackend(Protocol):
    provider: VectorStoreProvider
    supports_text_search: bool

    def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def health_check(self) -> None: ...

    async def create_collection(
        self,
        name: str,
        dimension: int,
        index_type: str = "HNSW",
        tenant_field: str | None = None,
    ) -> None: ...

    async def delete_collection(self, name: str) -> None: ...

    async def insert(
        self,
        collection: str,
        ids: list[str],
        document_ids: list[str],
        chunk_indices: list[int],
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict] | None = None,
    ) -> int: ...

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        filters: FilterExpression | None = None,
        payload_fields: list[str] | None = None,
    ) -> list[dict]: ...

    async def get_chunks(
        self,
        collection: str,
        document_id: str,
        limit: int = 10000,
        offset: int = 0,
    ) -> tuple[list[dict], int]: ...

    async def delete_by_document(self, collection: str, document_id: str) -> None: ...

    async def delete_by_ids(self, collection: str, ids: list[str]) -> None: ...

    async def text_search(
        self,
        collection: str,
        query_terms: list[str],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]: ...

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadata: list[dict] | None = None,
    ) -> int: ...

    async def export_collection_points(
        self,
        collection: str,
        *,
        with_vectors: bool = True,
    ) -> list[dict]: ...

    def iter_collection_points(
        self,
        collection: str,
        *,
        with_vectors: bool = True,
    ) -> AsyncIterator[dict]: ...


def _backend_name(prefix: str, name: str) -> str:
    return f"{prefix}{name}"


def _point_id(collection: str, value: str) -> str:
    return str(uuid.uuid5(_POINT_NAMESPACE, f"{collection}:{value}"))


def _build_payload(
    *,
    id_: str,
    document_id: str,
    chunk_index: int,
    text: str,
    metadata: dict | None = None,
) -> dict:
    payload = dict(metadata or {})
    payload.update(
        {
            "id": id_,
            "document_id": document_id,
            "chunk_index": chunk_index,
            "text": text,
        }
    )
    return payload


def _row_from_payload(point_id: str, score: float, payload: dict) -> dict:
    metadata = {
        k: v for k, v in payload.items() if k not in _FIXED_PAYLOAD_FIELDS and v is not None
    }
    return {
        "id": payload.get("id") or point_id,
        "score": score,
        "text": payload.get("text", ""),
        "document_id": payload.get("document_id"),
        "chunk_index": payload.get("chunk_index"),
        "metadata": metadata,
    }


def _chunk_rows_from_payloads(
    payloads: list[dict],
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    all_chunks = sorted(payloads, key=lambda payload: payload.get("chunk_index", 0))
    total = len(all_chunks)
    page = all_chunks[offset : offset + limit]
    return [
        {
            "id": payload.get("id", ""),
            "document_id": payload.get("document_id", ""),
            "text": payload.get("text", ""),
            "chunk_index": payload.get("chunk_index", 0),
            "metadata": {
                k: v for k, v in payload.items() if k not in _FIXED_PAYLOAD_FIELDS and v is not None
            },
        }
        for payload in page
    ], total
