from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag.types.admin import (
    CreateMcpServerBody,
    CreateMcpServerResponse,
    McpServer,
    McpServerListResponse,
    UpdateMcpServerBody,
)
from bigrag.types.common import StatusResponse

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminMcpServersResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(self) -> McpServerListResponse:
        return await self._client._request("GET", "/v1/admin/mcp-servers")

    async def create(self, body: CreateMcpServerBody) -> CreateMcpServerResponse:
        return await self._client._request("POST", "/v1/admin/mcp-servers", json=body)

    async def update(self, server_id: str, body: UpdateMcpServerBody) -> McpServer:
        return await self._client._request(
            "PATCH", f"/v1/admin/mcp-servers/{quote(server_id, safe='')}", json=body
        )

    async def rotate(self, server_id: str) -> CreateMcpServerResponse:
        return await self._client._request(
            "POST", f"/v1/admin/mcp-servers/{quote(server_id, safe='')}/rotate"
        )

    async def delete(self, server_id: str) -> StatusResponse:
        return await self._client._request(
            "DELETE", f"/v1/admin/mcp-servers/{quote(server_id, safe='')}"
        )
