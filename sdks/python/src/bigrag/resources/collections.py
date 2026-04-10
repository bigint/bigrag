"""Collection management resource."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag._errors import error_for_status
from bigrag._sse import parse_sse_stream
from bigrag.types.collections import (
    Collection,
    CollectionListResponse,
    CollectionStatsResponse,
    CreateCollectionBody,
    UpdateCollectionBody,
)
from bigrag.types.common import StatusResponse
from bigrag.types.sse import ProgressEvent

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore

_UA = "bigrag-python/0.0.1"


class CollectionsResource:
    """Resource namespace for collection management.

    Access via ``client.collections``.
    """

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(
        self,
        *,
        name: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> CollectionListResponse:
        """List collections with optional filtering and pagination."""
        params: dict[str, str] = {}
        if name is not None:
            params["name"] = name
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        return await self._client._request("GET", "/v1/collections", params=params)

    async def get(self, name: str) -> Collection:
        """Retrieve a single collection by name."""
        return await self._client._request(
            "GET", f"/v1/collections/{quote(name, safe='')}"
        )

    async def create(self, body: CreateCollectionBody) -> Collection:
        """Create a new collection."""
        return await self._client._request("POST", "/v1/collections", json=body)

    async def update(self, name: str, body: UpdateCollectionBody) -> Collection:
        """Update an existing collection."""
        return await self._client._request(
            "PUT", f"/v1/collections/{quote(name, safe='')}", json=body
        )

    async def delete(self, name: str) -> StatusResponse:
        """Delete a collection and all its documents."""
        return await self._client._request(
            "DELETE", f"/v1/collections/{quote(name, safe='')}"
        )

    async def stats(self, name: str) -> CollectionStatsResponse:
        """Get statistics for a collection."""
        return await self._client._request(
            "GET", f"/v1/collections/{quote(name, safe='')}/stats"
        )

    async def truncate(self, name: str) -> StatusResponse:
        """Truncate a collection — delete all documents, vectors, and S3 jobs."""
        return await self._client._request(
            "POST", f"/v1/collections/{quote(name, safe='')}/truncate"
        )

    async def stream_events(self, name: str) -> AsyncGenerator[ProgressEvent, None]:
        """Stream real-time events for a collection via SSE."""
        path = f"/v1/collections/{quote(name, safe='')}/events"
        token = (
            f"?token={quote(self._client.api_key, safe='')}"
            if self._client.api_key else ""
        )
        url = f"{self._client.base_url}{path}{token}"
        request = self._client._client.build_request(
            "GET", url, headers={"User-Agent": _UA},
        )
        response = await self._client._client.send(request, stream=True)
        if response.status_code >= 400:
            await response.aread()
            raise error_for_status(
                response.status_code,
                response.reason_phrase or "Unknown error",
            )
        async for event in parse_sse_stream(response):
            yield event
