from __future__ import annotations

from typing import Any

from turbopuffer import NotFoundError as TurbopufferNotFoundError

from bigrag.services._retrieval_filters import FilterExpression
from bigrag.services.vector_store.base import _chunk_rows, _row_from_payload
from bigrag.services.vector_store.turbopuffer.client import (
    _PUBLIC_ID_FIELD,
    _response_row,
    _row_payload,
    _to_turbopuffer_filter,
)


class _TurbopufferQueryMixin:
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
    ) -> list[dict]:
        doc_filter = ["document_id", "Eq", document_id]
        filters = (
            doc_filter if offset <= 0 else ["And", [doc_filter, ["chunk_index", "Gte", offset]]]
        )
        rows = await self._query_rows(
            collection,
            {
                "rank_by": ["chunk_index", "asc"],
                "filters": filters,
                "limit": {"total": limit},
                "exclude_attributes": ["vector"],
            },
        )
        return _chunk_rows([_row_payload(row) for row in rows])

    async def _query_rows(self, collection: str, payload: dict) -> list[dict]:
        try:
            response = await self._namespace_client(collection).query(**payload)
        except TurbopufferNotFoundError:
            return []
        return [_response_row(row) for row in response.rows]

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
