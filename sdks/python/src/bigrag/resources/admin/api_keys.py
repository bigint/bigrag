from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag.resources.admin._shared import _pagination
from bigrag.types.admin import (
    ApiKey,
    ApiKeyListResponse,
    CreateApiKeyBody,
    CreateApiKeyResponse,
    UpdateApiKeyBody,
)
from bigrag.types.common import StatusResponse

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminApiKeysResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> ApiKeyListResponse:
        params = _pagination(limit=limit, offset=offset)
        return await self._client._request("GET", "/v1/admin/api-keys", params=params)

    async def create(self, body: CreateApiKeyBody) -> CreateApiKeyResponse:
        return await self._client._request("POST", "/v1/admin/api-keys", json=body)

    async def update(self, key_id: str, body: UpdateApiKeyBody) -> ApiKey:
        return await self._client._request(
            "PATCH", f"/v1/admin/api-keys/{quote(key_id, safe='')}", json=body
        )

    async def rotate(self, key_id: str) -> CreateApiKeyResponse:
        return await self._client._request(
            "POST", f"/v1/admin/api-keys/{quote(key_id, safe='')}/rotate"
        )

    async def delete(self, key_id: str) -> StatusResponse:
        return await self._client._request("DELETE", f"/v1/admin/api-keys/{quote(key_id, safe='')}")
