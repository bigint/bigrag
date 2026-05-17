
from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag.types.query import (
    BatchQueryBody,
    BatchQueryResponse,
    MultiQueryBody,
    MultiQueryResponse,
    QueryBody,
    QueryResponse,
)

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class QueryResource:

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def query(self, collection: str, body: QueryBody) -> QueryResponse:
        return await self._client._request(
            "POST",
            f"/v1/collections/{quote(collection, safe='')}/query",
            json=body,
        )

    async def multi_query(self, body: MultiQueryBody) -> MultiQueryResponse:
        return await self._client._request("POST", "/v1/query", json=body)

    async def batch_query(self, body: BatchQueryBody) -> BatchQueryResponse:
        return await self._client._request("POST", "/v1/batch/query", json=body)
