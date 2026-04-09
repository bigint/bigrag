"""Collection management resource."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag.types.collections import (
    Collection,
    CollectionListResponse,
    CollectionStatsResponse,
    CreateCollectionBody,
    UpdateCollectionBody,
)
from bigrag.types.common import StatusResponse

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


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
