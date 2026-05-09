from __future__ import annotations

from typing import Any

import httpx

from bigrag.logging import get_logger
from bigrag.services._retrieval_filters import FilterCondition, FilterExpression
from bigrag.services.vector_store.base import (
    VectorStoreFeatureError,
    VectorStoreProvider,
    _backend_name,
    _build_payload,
    _chunk_rows_from_payloads,
    _point_id,
    _row_from_payload,
)

logger = get_logger("bigrag.vector_store")


def _to_turbopuffer_filter(filters: FilterExpression | None) -> list | None:
    if filters is None:
        return None
    clauses = [_to_turbopuffer_condition(condition) for condition in filters.conditions]
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return ["And", clauses]


def _to_turbopuffer_condition(condition: FilterCondition) -> list:
    op = {
        "eq": "Eq",
        "ne": "NotEq",
        "gt": "Gt",
        "gte": "Gte",
        "lt": "Lt",
        "lte": "Lte",
        "in": "In",
    }[condition.operator]
    return [condition.field, op, condition.value]


class TurbopufferVectorStore:
    provider: VectorStoreProvider = "turbopuffer"
    supports_text_search = False

    def __init__(
        self,
        *,
        api_key: str | None,
        region: str,
        namespace_prefix: str = "bigrag_",
    ) -> None:
        self.api_key = api_key
        self.region = region
        self.prefix = namespace_prefix or "bigrag_"
        self.client: httpx.AsyncClient | None = None

    def connect(self) -> None:
        if not self.api_key:
            raise RuntimeError("turbopuffer API key is not configured")
        base_url = f"https://{self.region}.turbopuffer.com"
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        logger.info("connected to turbopuffer", region=self.region)

    def _client(self) -> httpx.AsyncClient:
        if self.client is None:
            self.connect()
        if self.client is None:
            raise RuntimeError("turbopuffer client is not connected")
        return self.client

    def _namespace(self, name: str) -> str:
        return _backend_name(self.prefix, name)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def health_check(self) -> None:
        client = self._client()
        response = await client.get("/v1/namespaces")
        response.raise_for_status()

    async def create_collection(
        self,
        name: str,
        dimension: int,
        index_type: str = "HNSW",
        tenant_field: str | None = None,
    ) -> None:
        await self._write(
            name,
            {
                "upsert_rows": [],
                "distance_metric": "cosine_distance",
                "schema": {"vector": {"type": f"[{dimension}]f32", "ann": True}},
            },
        )

    async def delete_collection(self, name: str) -> None:
        client = self._client()
        response = await client.delete(f"/v1/namespaces/{self._namespace(name)}")
        if response.status_code == 404:
            return
        response.raise_for_status()

    async def insert(
        self,
        collection: str,
        ids: list[str],
        document_ids: list[str],
        chunk_indices: list[int],
        texts: list[str],
        embeddings: list[list[float]],
        metadata: list[dict] | None = None,
    ) -> int:
        namespace = self._namespace(collection)
        rows = []
        for i in range(len(ids)):
            payload = _build_payload(
                id_=ids[i],
                document_id=document_ids[i],
                chunk_index=chunk_indices[i],
                text=texts[i],
                metadata=metadata[i] if metadata else None,
            )
            rows.append({"id": _point_id(namespace, ids[i]), "vector": embeddings[i], **payload})
        await self._write(collection, {"upsert_rows": rows, "distance_metric": "cosine_distance"})
        return len(rows)

    async def _write(self, collection: str, payload: dict) -> dict:
        client = self._client()
        response = await client.post(f"/v2/namespaces/{self._namespace(collection)}", json=payload)
        response.raise_for_status()
        return response.json() if response.content else {}

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]:
        payload: dict[str, Any] = {
            "rank_by": ["vector", "ANN", query_embedding],
            "top_k": top_k,
            "include_attributes": True,
        }
        turbo_filter = _to_turbopuffer_filter(filters)
        if turbo_filter:
            payload["filters"] = turbo_filter
        client = self._client()
        response = await client.post(
            f"/v2/namespaces/{self._namespace(collection)}/query",
            json=payload,
        )
        response.raise_for_status()
        rows = []
        for row in response.json().get("rows", []):
            point_id = str(row.get("id", ""))
            distance = float(row.get("$dist", 0.0))
            payload_row = {k: v for k, v in row.items() if k not in {"$dist"}}
            rows.append(_row_from_payload(point_id, max(0.0, 1.0 - distance), payload_row))
        return rows

    async def get_chunks(
        self,
        collection: str,
        document_id: str,
        limit: int = 10000,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        rows = await self._query_rows(
            collection,
            {
                "rank_by": ["id", "asc"],
                "filters": ["document_id", "Eq", document_id],
                "limit": {"total": 10000},
                "include_attributes": True,
            },
        )
        return _chunk_rows_from_payloads(rows, limit, offset)

    async def _query_rows(self, collection: str, payload: dict) -> list[dict]:
        client = self._client()
        response = await client.post(
            f"/v2/namespaces/{self._namespace(collection)}/query",
            json=payload,
        )
        response.raise_for_status()
        return response.json().get("rows", [])

    async def delete_by_document(self, collection: str, document_id: str) -> None:
        await self._write(collection, {"delete_by_filter": ["document_id", "Eq", document_id]})

    async def delete_by_ids(self, collection: str, ids: list[str]) -> None:
        namespace = self._namespace(collection)
        await self._write(collection, {"deletes": [_point_id(namespace, id_) for id_ in ids]})

    async def text_search(
        self,
        collection: str,
        query_terms: list[str],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]:
        raise VectorStoreFeatureError("turbopuffer does not support keyword or hybrid search in v1")

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadata: list[dict] | None = None,
    ) -> int:
        return await self.insert(
            collection,
            ids,
            [""] * len(ids),
            [0] * len(ids),
            texts,
            embeddings,
            metadata,
        )

    async def export_collection_points(self, collection: str) -> list[dict]:
        rows = await self._query_rows(
            collection,
            {
                "rank_by": ["id", "asc"],
                "limit": {"total": 10000},
                "include_attributes": True,
            },
        )
        points = []
        for row in rows:
            points.append(
                {
                    "id": str(row.get("id", "")),
                    "payload": {k: v for k, v in row.items() if k not in {"id", "vector"}},
                    "vector": row.get("vector"),
                }
            )
        return points
