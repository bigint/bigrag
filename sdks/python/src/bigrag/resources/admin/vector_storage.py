from __future__ import annotations

from typing import TYPE_CHECKING

from bigrag.types.admin import VectorStorageOverviewResponse

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminVectorStorageResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def overview(self) -> VectorStorageOverviewResponse:
        return await self._client._request("GET", "/v1/admin/vector-storage/overview")
