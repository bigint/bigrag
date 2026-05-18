from __future__ import annotations

from typing import TYPE_CHECKING

from bigrag.types.admin import (
    InstanceSettingsResponse,
    InstanceSettingsTestResponse,
    ResetInstanceSettingsBody,
    TestInstanceSettingsBody,
    UpdateInstanceSettingsBody,
)
from bigrag.types.common import StatusResponse

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminSettingsResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(self) -> InstanceSettingsResponse:
        return await self._client._request("GET", "/v1/admin/settings")

    async def update(
        self, body: UpdateInstanceSettingsBody
    ) -> InstanceSettingsResponse:
        return await self._client._request("PUT", "/v1/admin/settings", json=body)

    async def test(
        self, body: TestInstanceSettingsBody | None = None
    ) -> InstanceSettingsTestResponse:
        values = (body or {}).get("values", {})
        return await self._client._request(
            "POST", "/v1/admin/settings/test", json={"values": values}
        )

    async def reset(
        self, body: ResetInstanceSettingsBody | None = None
    ) -> StatusResponse:
        return await self._client._request(
            "POST", "/v1/admin/settings/reset", json=body or {"keys": []}
        )

    async def purge_embedding_cache(self) -> StatusResponse:
        return await self._client._request(
            "POST", "/v1/admin/settings/embedding-cache/purge"
        )
