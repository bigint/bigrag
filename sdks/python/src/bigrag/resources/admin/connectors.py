from __future__ import annotations

from typing import TYPE_CHECKING

from bigrag.types.connectors import (
    GoogleConnectorConfig,
    UpdateGoogleConnectorConfigBody,
)

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminConnectorsResource:
    google: AdminGoogleConnectorResource

    def __init__(self, client: BigRAGCore) -> None:
        self.google = AdminGoogleConnectorResource(client)


class AdminGoogleConnectorResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def get(self) -> GoogleConnectorConfig:
        return await self._client._request("GET", "/v1/admin/connectors/google")

    async def update(
        self, body: UpdateGoogleConnectorConfigBody
    ) -> GoogleConnectorConfig:
        return await self._client._request(
            "PUT", "/v1/admin/connectors/google", json=body
        )
