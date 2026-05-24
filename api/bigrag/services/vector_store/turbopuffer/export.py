from __future__ import annotations

from typing import Any

from bigrag.services.vector_store.turbopuffer.client import _EXPORT_PAGE_SIZE, _row_payload


class _TurbopufferExportMixin:
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
