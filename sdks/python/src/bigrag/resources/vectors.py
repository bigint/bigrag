"""Raw vector operations resource."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag._types import DeleteResponse, UpsertResponse, VectorEntry

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class VectorsResource:
    """Resource namespace for raw vector operations.

    Access via ``client.vectors``.
    """

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def upsert(
        self, collection: str, vectors: list[VectorEntry]
    ) -> UpsertResponse:
        """Upsert vectors into a collection."""
        return await self._client._request(
            "POST",
            f"/v1/collections/{quote(collection, safe='')}/vectors/upsert",
            json={"vectors": vectors},
        )

    async def delete(self, collection: str, ids: list[str]) -> DeleteResponse:
        """Delete vectors from a collection by ID."""
        return await self._client._request(
            "POST",
            f"/v1/collections/{quote(collection, safe='')}/vectors/delete",
            json={"ids": ids},
        )
