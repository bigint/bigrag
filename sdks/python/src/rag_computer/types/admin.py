"""Admin API types."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict
from rag_computer.types.auth import User


class UserListResponse(TypedDict):
    users: list[User]
    total: int


class CreateUserBody(TypedDict):
    email: str
    password: str
    display_name: NotRequired[str]
    role: NotRequired[str]


class UpdateUserBody(TypedDict, total=False):
    display_name: str
    role: str
    password: str


class ApiKey(TypedDict):
    id: str
    name: str
    prefix: str
    active: bool
    scopes: list[str]
    collection: str | None
    last_used_at: str | None
    expires_at: str | None
    created_at: str
    updated_at: str


class CreateApiKeyBody(TypedDict):
    name: str
    expires_at: NotRequired[str | None]
    scopes: NotRequired[list[str] | None]
    collection: NotRequired[str | None]


class CreateApiKeyResponse(ApiKey):
    key: str


class UpdateApiKeyBody(TypedDict, total=False):
    name: str
    active: bool
    scopes: list[str] | None
    collection: str | None


class ApiKeyListResponse(TypedDict):
    keys: list[ApiKey]
    total: int


class AuditLogEntry(TypedDict):
    id: str
    actor_id: str | None
    actor_email: str | None
    api_key_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    metadata: dict[str, Any]
    ip: str | None
    user_agent: str | None
    created_at: str


class AuditLogListResponse(TypedDict):
    entries: list[AuditLogEntry]
    total: int


class EmbeddingPreset(TypedDict):
    id: str
    name: str
    provider: str
    model: str
    base_url: str | None
    dimension: int
    has_api_key: bool
    created_at: str
    updated_at: str


class CreateEmbeddingPresetBody(TypedDict):
    name: str
    provider: str
    model: str
    api_key: str
    dimension: int
    base_url: NotRequired[str | None]


class UpdateEmbeddingPresetBody(TypedDict, total=False):
    name: str
    provider: str
    model: str
    api_key: str
    base_url: str | None
    dimension: int


class EmbeddingPresetListResponse(TypedDict):
    presets: list[EmbeddingPreset]
    total: int


class McpServer(TypedDict):
    id: str
    title: str
    server_name: str
    collection: str | None
    key_prefix: str
    key_active: bool
    last_used_at: str | None
    created_at: str
    updated_at: str


class CreateMcpServerBody(TypedDict):
    title: str
    server_name: str
    collection: NotRequired[str | None]


class UpdateMcpServerBody(TypedDict, total=False):
    title: str
    server_name: str
    collection: str | None


class CreateMcpServerResponse(McpServer):
    api_key: str


class McpServerListResponse(TypedDict):
    servers: list[McpServer]
    total: int
