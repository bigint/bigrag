"""Admin API resources."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, AsyncGenerator
from urllib.parse import quote

from bigrag.types.access import AccessLogListResponse, AccessLogOverviewResponse
from bigrag.types.admin import (
    AdminRealtimeEvent,
    ApiKey,
    ApiKeyListResponse,
    AuditLogListResponse,
    BackupCreateBody,
    BackupJob,
    BackupJobListResponse,
    CreateApiKeyBody,
    CreateApiKeyResponse,
    CreateEmbeddingPresetBody,
    CreateMcpServerBody,
    CreateMcpServerResponse,
    CreateUserBody,
    EmbeddingPreset,
    EmbeddingPresetListResponse,
    InstanceSettingsResponse,
    InstanceSettingsTestResponse,
    McpServer,
    McpServerListResponse,
    ResetInstanceSettingsBody,
    TestInstanceSettingsBody,
    UpdateApiKeyBody,
    UpdateEmbeddingPresetBody,
    UpdateInstanceSettingsBody,
    UpdateMcpServerBody,
    UpdateUserBody,
    UserListResponse,
)
from bigrag.types.auth import User
from bigrag.types.common import StatusResponse
from bigrag.types.connectors import (
    GoogleConnectorConfig,
    UpdateGoogleConnectorConfigBody,
)

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminResource:
    """Container for session-only admin resources."""

    users: AdminUsersResource
    api_keys: AdminApiKeysResource
    access: AdminAccessResource
    audit: AdminAuditResource
    backups: AdminBackupsResource
    connectors: AdminConnectorsResource
    embedding_presets: AdminEmbeddingPresetsResource
    mcp_servers: AdminMcpServersResource
    realtime: AdminRealtimeResource
    settings: AdminSettingsResource

    def __init__(self, client: BigRAGCore) -> None:
        self.users = AdminUsersResource(client)
        self.api_keys = AdminApiKeysResource(client)
        self.access = AdminAccessResource(client)
        self.audit = AdminAuditResource(client)
        self.backups = AdminBackupsResource(client)
        self.connectors = AdminConnectorsResource(client)
        self.embedding_presets = AdminEmbeddingPresetsResource(client)
        self.mcp_servers = AdminMcpServersResource(client)
        self.realtime = AdminRealtimeResource(client)
        self.settings = AdminSettingsResource(client)


class AdminSettingsResource:
    """Admin runtime settings."""

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(self) -> InstanceSettingsResponse:
        """List runtime settings."""
        return await self._client._request("GET", "/v1/admin/settings")

    async def update(
        self, body: UpdateInstanceSettingsBody
    ) -> InstanceSettingsResponse:
        """Update runtime settings."""
        return await self._client._request("PUT", "/v1/admin/settings", json=body)

    async def test(
        self, body: TestInstanceSettingsBody | None = None
    ) -> InstanceSettingsTestResponse:
        """Test runtime settings."""
        values = (body or {}).get("values", {})
        return await self._client._request(
            "POST", "/v1/admin/settings/test", json={"values": values}
        )

    async def reset(
        self, body: ResetInstanceSettingsBody | None = None
    ) -> StatusResponse:
        """Reset runtime settings."""
        return await self._client._request(
            "POST", "/v1/admin/settings/reset", json=body or {"keys": []}
        )

    async def purge_embedding_cache(self) -> StatusResponse:
        """Purge the embedding model cache."""
        return await self._client._request(
            "POST", "/v1/admin/settings/embedding-cache/purge"
        )


class AdminBackupsResource:
    """Admin backups."""

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> BackupJobListResponse:
        """List backup jobs."""
        params = _pagination(limit=limit, offset=offset)
        return await self._client._request("GET", "/v1/admin/backups", params=params)

    async def get(self, backup_id: str) -> BackupJob:
        """Get a backup job."""
        return await self._client._request(
            "GET", f"/v1/admin/backups/{quote(backup_id, safe='')}"
        )

    async def create(self, body: BackupCreateBody | None = None) -> BackupJob:
        """Create a backup job."""
        label = (body or {}).get("label", "")
        return await self._client._request(
            "POST", "/v1/admin/backups", json={"label": label}
        )


class AdminRealtimeResource:
    """Admin realtime SSE streams."""

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    def documents(
        self,
        collection: str,
        *,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            f"/v1/admin/realtime/collections/{quote(collection, safe='')}/documents",
            {"status": status, "limit": limit, "offset": offset},
        )

    def document_batch_status(
        self, collection: str, document_ids: list[str]
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            f"/v1/admin/realtime/collections/{quote(collection, safe='')}/documents/batch-status",
            {"document_ids": ",".join(document_ids)},
        )

    def document(
        self, collection: str, document_id: str
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            f"/v1/admin/realtime/collections/{quote(collection, safe='')}/documents/{quote(document_id, safe='')}"
        )

    def upload_session(
        self, collection: str, session_id: str
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            f"/v1/admin/realtime/collections/{quote(collection, safe='')}/upload-sessions/{quote(session_id, safe='')}"
        )

    def collection_stats(
        self, collection: str
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            f"/v1/admin/realtime/collections/{quote(collection, safe='')}/stats"
        )

    def connector_sources(
        self, provider: str, *, collection: str | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            f"/v1/admin/realtime/{quote(provider, safe='')}/sources",
            {"collection": collection},
        )

    def connector_sync_jobs(
        self,
        provider: str,
        *,
        collection: str | None = None,
        source_id: str | None = None,
        limit: int | None = None,
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            f"/v1/admin/realtime/{quote(provider, safe='')}/sync-jobs",
            {"collection": collection, "source_id": source_id, "limit": limit},
        )

    def backups(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream("/v1/admin/realtime/backups", {"limit": limit, "offset": offset})

    def access_overview(
        self, *, window_days: int | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            "/v1/admin/realtime/access/overview", {"window_days": window_days}
        )

    def access_logs(
        self,
        *,
        action: str | None = None,
        actor_id: str | None = None,
        collection: str | None = None,
        method: str | None = None,
        path: str | None = None,
        status_family: str | None = None,
        success: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            "/v1/admin/realtime/access/logs",
            {
                "action": action,
                "actor_id": actor_id,
                "collection": collection,
                "method": method,
                "path": path,
                "status_family": status_family,
                "success": success,
                "limit": limit,
                "offset": offset,
            },
        )

    def audit(
        self,
        *,
        action: str | None = None,
        actor_id: str | None = None,
        resource_type: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(
            "/v1/admin/realtime/audit",
            {
                "action": action,
                "actor_id": actor_id,
                "resource_type": resource_type,
                "limit": limit,
                "offset": offset,
            },
        )

    def usage(
        self, *, window_days: int | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream("/v1/admin/realtime/usage", {"window_days": window_days})

    def platform_stats(self) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream("/v1/admin/realtime/platform/stats")

    def platform_readiness(self) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream("/v1/admin/realtime/platform/readiness")

    def custom(
        self, path: str, params: dict[str, str | int | bool | None] | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        return self._stream(path, params or {})

    async def _stream(
        self, path: str, params: dict[str, str | int | bool | None] | None = None
    ) -> AsyncGenerator[AdminRealtimeEvent, None]:
        query = _stream_params(params or {})
        async with self._client._client.stream(
            "GET",
            f"{self._client.base_url}{path}",
            params=query,
            headers=self._client._headers(),
            timeout=self._client.timeout,
        ) as response:
            if response.status_code >= 400:
                await response.aread()
                await self._client._throw_for_status(response)
            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk
                while True:
                    frame = _pop_sse_frame(buffer)
                    if frame is None:
                        break
                    block, buffer = frame
                    event = _parse_realtime_frame(block)
                    if event is not None:
                        yield event
            if buffer.strip():
                event = _parse_realtime_frame(buffer)
                if event is not None:
                    yield event


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


class AdminAccessResource:
    """Admin access log analytics."""

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def logs(
        self,
        *,
        action: str | None = None,
        actor_id: str | None = None,
        collection: str | None = None,
        method: str | None = None,
        path: str | None = None,
        status_family: str | None = None,
        success: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> AccessLogListResponse:
        """List RAG access log entries."""
        params = _pagination(limit=limit, offset=offset)
        if action is not None:
            params["action"] = action
        if actor_id is not None:
            params["actor_id"] = actor_id
        if collection is not None:
            params["collection"] = collection
        if method is not None:
            params["method"] = method
        if path is not None:
            params["path"] = path
        if status_family is not None:
            params["status_family"] = status_family
        if success is not None:
            params["success"] = "true" if success else "false"
        return await self._client._request(
            "GET", "/v1/admin/access/logs", params=params
        )

    async def overview(
        self, *, window_days: int | None = None
    ) -> AccessLogOverviewResponse:
        """Retrieve access log overview metrics."""
        params: dict[str, str] = {}
        if window_days is not None:
            params["window_days"] = str(window_days)
        return await self._client._request(
            "GET", "/v1/admin/access/overview", params=params
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


class AdminConnectorsResource:
    """Admin connector configuration resources."""

    google: AdminGoogleConnectorResource

    def __init__(self, client: BigRAGCore) -> None:
        self.google = AdminGoogleConnectorResource(client)


class AdminGoogleConnectorResource:
    """Admin Google Drive connector configuration."""

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def get(self) -> GoogleConnectorConfig:
        """Get Google Drive connector config."""
        return await self._client._request("GET", "/v1/admin/connectors/google")

    async def update(
        self, body: UpdateGoogleConnectorConfigBody
    ) -> GoogleConnectorConfig:
        """Update Google Drive connector config."""
        return await self._client._request(
            "PUT", "/v1/admin/connectors/google", json=body
        )


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


def _stream_params(params: dict[str, str | int | bool | None]) -> dict[str, str]:
    query: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            query[key] = "true" if value else "false"
        else:
            query[key] = str(value)
    return query


def _pop_sse_frame(buffer: str) -> tuple[str, str] | None:
    lf = buffer.find("\n\n")
    crlf = buffer.find("\r\n\r\n")
    if lf == -1 and crlf == -1:
        return None
    if lf != -1 and (crlf == -1 or lf < crlf):
        return buffer[:lf], buffer[lf + 2 :]
    return buffer[:crlf], buffer[crlf + 4 :]


def _parse_realtime_frame(frame: str) -> AdminRealtimeEvent | None:
    event = "message"
    data: list[str] = []
    for raw_line in frame.splitlines():
        line = raw_line.rstrip("\r")
        if not line or line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[6:].lstrip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if not data:
        return None
    payload = "\n".join(data)
    if payload == "[DONE]":
        return None
    return {"event": event, "data": json.loads(payload)}
