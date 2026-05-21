from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag.resources.admin._shared import _pagination
from bigrag.types.admin import (
    VectorMigrationCreateBody,
    VectorMigrationJob,
    VectorMigrationJobListResponse,
)
from bigrag.types.common import StatusResponse

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminVectorMigrationsResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(
        self,
        *,
        collection: str | None = None,
        cursor: str | None = None,
        include_total: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> VectorMigrationJobListResponse:
        params = _pagination(limit=limit, offset=offset)
        if collection is not None:
            params["collection"] = collection
        if cursor is not None:
            params["cursor"] = cursor
        if include_total is not None:
            params["include_total"] = "true" if include_total else "false"
        return await self._client._request(
            "GET", "/v1/admin/vector-storage/migrations", params=params
        )

    async def get(self, migration_id: str) -> VectorMigrationJob:
        return await self._client._request(
            "GET", f"/v1/admin/vector-storage/migrations/{quote(migration_id, safe='')}"
        )

    async def create(self, body: VectorMigrationCreateBody) -> VectorMigrationJob:
        return await self._client._request(
            "POST", "/v1/admin/vector-storage/migrations", json=body
        )

    async def delete(self, migration_id: str) -> StatusResponse:
        return await self._client._request(
            "DELETE",
            f"/v1/admin/vector-storage/migrations/{quote(migration_id, safe='')}",
        )
