"""Admin API resources."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag.types.admin import (
    ApiKey,
    ApiKeyListResponse,
    AuditLogListResponse,
    CreateApiKeyBody,
    CreateApiKeyResponse,
    CreateEmbeddingPresetBody,
    CreateMcpServerBody,
    CreateMcpServerResponse,
    CreateUserBody,
    EmbeddingPreset,
    EmbeddingPresetListResponse,
    McpServer,
    McpServerListResponse,
    UpdateApiKeyBody,
    UpdateEmbeddingPresetBody,
    UpdateMcpServerBody,
    UpdateUserBody,
    UserListResponse,
)
from bigrag.types.auth import User
from bigrag.types.common import StatusResponse

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminResource:
    """Container for session-only admin resources."""

    users: AdminUsersResource
    api_keys: AdminApiKeysResource
    audit: AdminAuditResource
    embedding_presets: AdminEmbeddingPresetsResource
    mcp_servers: AdminMcpServersResource

    def __init__(self, client: BigRAGCore) -> None:
        self.users = AdminUsersResource(client)
        self.api_keys = AdminApiKeysResource(client)
        self.audit = AdminAuditResource(client)
        self.embedding_presets = AdminEmbeddingPresetsResource(client)
        self.mcp_servers = AdminMcpServersResource(client)


class AdminUsersResource:
    """Admin user management."""

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> UserListResponse:
        """List admin UI users."""
        params = _pagination(limit=limit, offset=offset)
        return await self._client._request("GET", "/v1/admin/users", params=params)

    async def create(self, body: CreateUserBody) -> User:
        """Create an admin UI user."""
        return await self._client._request("POST", "/v1/admin/users", json=body)

    async def update(self, user_id: str, body: UpdateUserBody) -> User:
        """Update an admin UI user."""
        return await self._client._request(
            "PATCH", f"/v1/admin/users/{quote(user_id, safe='')}", json=body
        )

    async def delete(self, user_id: str) -> StatusResponse:
        """Delete an admin UI user."""
        return await self._client._request(
            "DELETE", f"/v1/admin/users/{quote(user_id, safe='')}"
        )


class AdminApiKeysResource:
    """Admin API key management."""

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> ApiKeyListResponse:
        """List API keys."""
        params = _pagination(limit=limit, offset=offset)
        return await self._client._request("GET", "/v1/admin/api-keys", params=params)

    async def create(self, body: CreateApiKeyBody) -> CreateApiKeyResponse:
        """Create an API key. The plaintext key is returned once."""
        return await self._client._request("POST", "/v1/admin/api-keys", json=body)

    async def update(self, key_id: str, body: UpdateApiKeyBody) -> ApiKey:
        """Update an API key."""
        return await self._client._request(
            "PATCH", f"/v1/admin/api-keys/{quote(key_id, safe='')}", json=body
        )

    async def delete(self, key_id: str) -> StatusResponse:
        """Delete an API key."""
        return await self._client._request(
            "DELETE", f"/v1/admin/api-keys/{quote(key_id, safe='')}"
        )


class AdminAuditResource:
    """Admin audit log access."""

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(
        self,
        *,
        action: str | None = None,
        actor_id: str | None = None,
        resource_type: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> AuditLogListResponse:
        """List audit log entries."""
        params = _pagination(limit=limit, offset=offset)
        if action is not None:
            params["action"] = action
        if actor_id is not None:
            params["actor_id"] = actor_id
        if resource_type is not None:
            params["resource_type"] = resource_type
        return await self._client._request("GET", "/v1/admin/audit", params=params)


class AdminEmbeddingPresetsResource:
    """Admin embedding preset management."""

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> EmbeddingPresetListResponse:
        """List embedding presets."""
        params = _pagination(limit=limit, offset=offset)
        return await self._client._request(
            "GET", "/v1/admin/embedding-presets", params=params
        )

    async def create(self, body: CreateEmbeddingPresetBody) -> EmbeddingPreset:
        """Create an embedding preset."""
        return await self._client._request(
            "POST", "/v1/admin/embedding-presets", json=body
        )

    async def update(
        self, preset_id: str, body: UpdateEmbeddingPresetBody
    ) -> EmbeddingPreset:
        """Update an embedding preset."""
        return await self._client._request(
            "PATCH",
            f"/v1/admin/embedding-presets/{quote(preset_id, safe='')}",
            json=body,
        )

    async def delete(self, preset_id: str) -> StatusResponse:
        """Delete an embedding preset."""
        return await self._client._request(
            "DELETE", f"/v1/admin/embedding-presets/{quote(preset_id, safe='')}"
        )


class AdminMcpServersResource:
    """Admin MCP server key management."""

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(self) -> McpServerListResponse:
        """List MCP server configs."""
        return await self._client._request("GET", "/v1/admin/mcp-servers")

    async def create(self, body: CreateMcpServerBody) -> CreateMcpServerResponse:
        """Create an MCP server config. The plaintext API key is returned once."""
        return await self._client._request("POST", "/v1/admin/mcp-servers", json=body)

    async def update(self, server_id: str, body: UpdateMcpServerBody) -> McpServer:
        """Update an MCP server config."""
        return await self._client._request(
            "PATCH", f"/v1/admin/mcp-servers/{quote(server_id, safe='')}", json=body
        )

    async def rotate(self, server_id: str) -> CreateMcpServerResponse:
        """Rotate an MCP server API key. The plaintext key is returned once."""
        return await self._client._request(
            "POST", f"/v1/admin/mcp-servers/{quote(server_id, safe='')}/rotate"
        )

    async def delete(self, server_id: str) -> StatusResponse:
        """Delete an MCP server config."""
        return await self._client._request(
            "DELETE", f"/v1/admin/mcp-servers/{quote(server_id, safe='')}"
        )


def _pagination(*, limit: int | None, offset: int | None) -> dict[str, str]:
    params: dict[str, str] = {}
    if limit is not None:
        params["limit"] = str(limit)
    if offset is not None:
        params["offset"] = str(offset)
    return params
