from __future__ import annotations

import uuid
from typing import Protocol

from bigrag.services._retrieval_filters import FilterExpression

_POINT_NAMESPACE = uuid.UUID("1b04f7ca-0c3b-5d76-a5bb-6e4b4a40f61d")
_FIXED_PAYLOAD_FIELDS = {"id", "text", "document_id", "chunk_index", "embedding"}


class VectorStoreBackend(Protocol):
    def connect(self) -> None: ...

    async def close(self) -> None: ...

    async def health_check(self) -> None: ...

    async def create_collection(
        self,
        name: str,
        dimension: int,
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
    ) -> list[dict]: ...

    async def delete_by_document(self, collection: str, document_id: str) -> None: ...

    async def delete_by_documents(self, collection: str, document_ids: list[str]) -> None: ...

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


def _chunk_rows(payloads: list[dict]) -> list[dict]:
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
        for payload in payloads
    ]
