from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag.types.vectors import DeleteResponse, UpsertResponse, VectorEntry

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class VectorsResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def upsert(
        self, collection: str, vectors: list[VectorEntry]
    ) -> UpsertResponse:
        return await self._client._request(
            "POST",
            f"/v1/collections/{quote(collection, safe='')}/vectors/upsert",
            json={"vectors": vectors},
        )

    async def delete(self, collection: str, ids: list[str]) -> DeleteResponse:
        return await self._client._request(
            "POST",
            f"/v1/collections/{quote(collection, safe='')}/vectors/delete",
            json={"ids": ids},
        )
