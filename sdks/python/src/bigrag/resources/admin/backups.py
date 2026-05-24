from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag.resources.admin._shared import _pagination
from bigrag.types.admin import (
    BackupCreateBody,
    BackupJob,
    BackupJobListResponse,
)

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminBackupsResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> BackupJobListResponse:
        params = _pagination(limit=limit, offset=offset)
        return await self._client._request("GET", "/v1/admin/backups", params=params)

    async def get(self, backup_id: str) -> BackupJob:
        return await self._client._request("GET", f"/v1/admin/backups/{quote(backup_id, safe='')}")

    async def create(self, body: BackupCreateBody | None = None) -> BackupJob:
        label = (body or {}).get("label", "")
        return await self._client._request("POST", "/v1/admin/backups", json={"label": label})
