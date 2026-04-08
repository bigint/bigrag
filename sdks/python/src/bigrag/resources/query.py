"""Query resource."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag._types import (
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
    """Resource namespace for query operations.

    Access via ``client.queries``.
    """

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def query(self, collection: str, body: QueryBody) -> QueryResponse:
        """Query a single collection."""
        return await self._client._request(
            "POST",
            f"/v1/collections/{quote(collection, safe='')}/query",
            json=body,
        )

    async def multi_query(self, body: MultiQueryBody) -> MultiQueryResponse:
        """Query across multiple collections simultaneously."""
        return await self._client._request("POST", "/v1/query", json=body)

    async def batch_query(self, body: BatchQueryBody) -> BatchQueryResponse:
        """Execute multiple queries in a single batch request."""
        return await self._client._request("POST", "/v1/batch/query", json=body)
