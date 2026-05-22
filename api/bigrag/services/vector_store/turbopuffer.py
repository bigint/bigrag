from __future__ import annotations

from typing import Any

from turbopuffer import AsyncTurbopuffer
from turbopuffer import NotFoundError as TurbopufferNotFoundError

from bigrag.logging import get_logger
from bigrag.services._retrieval_filters import FilterCondition, FilterExpression
from bigrag.services.vector_store.base import (
    _backend_name,
    _build_payload,
    _chunk_rows_from_payloads,
    _point_id,
    _row_from_payload,
)

logger = get_logger("bigrag.vector_store")

_PUBLIC_ID_FIELD = "bigrag_id"
_EXPORT_PAGE_SIZE = 10000


def _to_turbopuffer_filter(filters: FilterExpression | None) -> tuple | None:
    if filters is None:
        return None
    clauses = [_to_turbopuffer_condition(condition) for condition in filters.conditions]
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return ("And", tuple(clauses))


def _to_turbopuffer_condition(condition: FilterCondition) -> tuple:
    field = _PUBLIC_ID_FIELD if condition.field == "id" else condition.field
    op = {
        "eq": "Eq",
        "ne": "NotEq",
        "gt": "Gt",
        "gte": "Gte",
        "lt": "Lt",
        "lte": "Lte",
        "in": "In",
    }[condition.operator]
    return (field, op, condition.value)


def _schema(dimension: int) -> dict:
    return {
        "vector": {"type": f"[{dimension}]f32", "ann": True},
        _PUBLIC_ID_FIELD: {"type": "string"},
        "document_id": {"type": "string"},
        "chunk_index": {"type": "int"},
        "text": {"type": "string", "full_text_search": True},
    }


def _row_payload(row: dict) -> dict:
    payload = {
        k: v
        for k, v in row.items()
        if k not in {"$dist", "vector", _PUBLIC_ID_FIELD} and v is not None
    }
    payload["id"] = row.get(_PUBLIC_ID_FIELD) or row.get("id")
    return payload


def _response_row(row: Any) -> dict:
    if isinstance(row, dict):
        return row
    if hasattr(row, "to_dict"):
        return row.to_dict()
    if hasattr(row, "model_dump"):
        return row.model_dump(mode="json", by_alias=True)
    return dict(row)


class TurbopufferVectorStore:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        region: str = "aws-us-east-1",
        namespace_prefix: str = "bigrag_",
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.region = region
        self.prefix = namespace_prefix or "bigrag_"
        self.base_url = base_url.rstrip("/") if base_url else None
        self.client: AsyncTurbopuffer | None = None

    def connect(self) -> None:
        if not self.api_key:
            raise RuntimeError("turbopuffer API key is not configured")
        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        else:
            kwargs["region"] = self.region
        self.client = AsyncTurbopuffer(
            **kwargs,
            max_retries=2,
            timeout=30,
        )
        logger.info("connected to turbopuffer", region=self.region, base_url=self.base_url)

    def _client(self) -> AsyncTurbopuffer:
        if self.client is None:
            self.connect()
        if self.client is None:
            raise RuntimeError("turbopuffer client is not connected")
        return self.client

    def _namespace_client(self, name: str):
        return self._client().namespace(self._namespace(name))

    def _namespace(self, name: str) -> str:
        return _backend_name(self.prefix, name)

    def _point_id(self, collection: str, value: str) -> str:
        return _point_id(self._namespace(collection), value)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
            self.client = None

    async def health_check(self) -> None:
        async for _ in self._client().namespaces(prefix=self.prefix, page_size=1):
            break

    async def create_collection(
        self,
        name: str,
        dimension: int,
        tenant_field: str | None = None,
    ) -> None:
        await self.health_check()

    async def delete_collection(self, name: str) -> None:
        try:
            await self._namespace_client(name).delete_all()
        except TurbopufferNotFoundError:
            return

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
        rows = []
        for i in range(len(ids)):
            payload = _build_payload(
                id_=ids[i],
                document_id=document_ids[i],
                chunk_index=chunk_indices[i],
                text=texts[i],
                metadata=metadata[i] if metadata else None,
            )
            public_id = payload.pop("id")
            payload[_PUBLIC_ID_FIELD] = public_id
            rows.append(
                {
                    "id": self._point_id(collection, ids[i]),
                    "vector": embeddings[i],
                    **payload,
                }
            )
        write_payload: dict[str, Any] = {
            "upsert_rows": rows,
            "distance_metric": "cosine_distance",
        }
        if embeddings:
            dimension = len(embeddings[0])
            write_payload["schema"] = _schema(dimension)
        await self._write(collection, write_payload)
        return len(rows)

    async def _write(self, collection: str, payload: dict) -> dict:
        response = await self._namespace_client(collection).write(**payload)
        if hasattr(response, "to_dict"):
            return response.to_dict()
        return {}

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        filters: FilterExpression | None = None,
        payload_fields: list[str] | None = None,
    ) -> list[dict]:
        payload: dict[str, Any] = {
            "rank_by": ["vector", "ANN", query_embedding],
            "top_k": top_k,
        }
        if payload_fields:
            attrs = [_PUBLIC_ID_FIELD if f == "id" else f for f in payload_fields]
            payload["include_attributes"] = attrs
        else:
            payload["exclude_attributes"] = ["vector"]
        turbo_filter = _to_turbopuffer_filter(filters)
        if turbo_filter:
            payload["filters"] = turbo_filter
        rows = []
        for row in await self._query_rows(collection, payload):
            point_id = str(row.get("id", ""))
            distance = float(row.get("$dist", 0.0))
            rows.append(_row_from_payload(point_id, max(0.0, 1.0 - distance), _row_payload(row)))
        return rows

    async def get_chunks(
        self,
        collection: str,
        document_id: str,
        limit: int = 10000,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        rows: list[dict] = []
        last_id: str | None = None
        while True:
            doc_filter = ["document_id", "Eq", document_id]
            filters = (
                doc_filter if last_id is None else ["And", [doc_filter, ["id", "Gt", last_id]]]
            )
            page = await self._query_rows(
                collection,
                {
                    "rank_by": ["id", "asc"],
                    "filters": filters,
                    "limit": {"total": _EXPORT_PAGE_SIZE},
                    "exclude_attributes": ["vector"],
                },
            )
            rows.extend(page)
            if len(page) < _EXPORT_PAGE_SIZE:
                break
            last_id = str(page[-1].get("id", ""))
        return _chunk_rows_from_payloads([_row_payload(row) for row in rows], limit, offset)

    async def _query_rows(self, collection: str, payload: dict) -> list[dict]:
        try:
            response = await self._namespace_client(collection).query(**payload)
        except TurbopufferNotFoundError:
            return []
        return [_response_row(row) for row in response.rows]

    async def delete_by_document(self, collection: str, document_id: str) -> None:
        try:
            await self._write(collection, {"delete_by_filter": ["document_id", "Eq", document_id]})
        except TurbopufferNotFoundError:
            return

    async def delete_by_ids(self, collection: str, ids: list[str]) -> None:
        try:
            deletes = [self._point_id(collection, id_) for id_ in ids]
            await self._write(collection, {"deletes": deletes})
        except TurbopufferNotFoundError:
            return

    async def text_search(
        self,
        collection: str,
        query_terms: list[str],
        top_k: int = 10,
        filters: FilterExpression | None = None,
    ) -> list[dict]:
        query = " ".join(term for term in query_terms if term).strip()
        if not query:
            return []
        payload: dict[str, Any] = {
            "rank_by": ["text", "BM25", query],
            "top_k": top_k,
            "exclude_attributes": ["vector"],
        }
        turbo_filter = _to_turbopuffer_filter(filters)
        if turbo_filter:
            payload["filters"] = turbo_filter
        rows = await self._query_rows(collection, payload)
        results = []
        for row in rows:
            point_id = str(row.get("id", ""))
            score = row.get("$score")
            if score is None:
                score = max(0.0, 1.0 - float(row.get("$dist", 0.0)))
            results.append(_row_from_payload(point_id, float(score), _row_payload(row)))
        return results

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

    async def export_collection_points(
        self,
        collection: str,
        *,
        with_vectors: bool = True,
    ) -> list[dict]:
        return [
            point
            async for point in self.iter_collection_points(collection, with_vectors=with_vectors)
        ]

    async def iter_collection_points(
        self,
        collection: str,
        *,
        with_vectors: bool = True,
    ):
        last_id: str | None = None
        while True:
            payload: dict[str, Any] = {
                "rank_by": ["id", "asc"],
                "limit": {"total": _EXPORT_PAGE_SIZE},
            }
            if with_vectors:
                payload["include_attributes"] = True
            else:
                payload["exclude_attributes"] = ["vector"]
            if last_id is not None:
                payload["filters"] = ["id", "Gt", last_id]
            rows = await self._query_rows(collection, payload)
            for row in rows:
                yield {
                    "id": str(row.get("id", "")),
                    "payload": _row_payload(row),
                    "vector": row.get("vector") if with_vectors else None,
                }
            if len(rows) < _EXPORT_PAGE_SIZE:
                break
            last_id = str(rows[-1].get("id", ""))
