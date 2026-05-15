"""Admin API types."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict
from bigrag.types.auth import User

InstanceSettingKind = Literal[
    "bool",
    "int",
    "float",
    "string",
    "string_list",
    "int_list",
    "select",
    "secret",
]

InstanceSettingGroup = Literal[
    "security",
    "ingestion",
    "storage",
    "vector_store",
    "queue",
    "search",
    "chat",
    "webhooks",
    "retention",
    "backups",
]


class InstanceSettingSpec(TypedDict):
    key: str
    group: InstanceSettingGroup
    label: str
    description: str
    kind: InstanceSettingKind
    default: Any
    options: list[str]
    min: float | None
    max: float | None
    secret: bool


class InstanceSetting(TypedDict):
    key: str
    value: Any
    has_value: bool
    source: str
    updated_at: str | None
    updated_by: str | None


class InstanceSettingsResponse(TypedDict):
    specs: list[InstanceSettingSpec]
    values: dict[str, InstanceSetting]


class UpdateInstanceSettingsBody(TypedDict):
    values: dict[str, Any]


class ResetInstanceSettingsBody(TypedDict):
    keys: list[str]


class TestInstanceSettingsBody(TypedDict, total=False):
    values: dict[str, Any]


class InstanceSettingsTestResponse(TypedDict):
    status: str
    checked: list[str]
    message: str


class BackupCreateBody(TypedDict, total=False):
    label: str


class BackupJob(TypedDict):
    id: str
    label: str
    status: str
    progress: float
    destination_prefix: str
    object_count: int
    byte_count: int
    manifest: dict[str, Any]
    error_message: str | None
    created_by: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str
    updated_at: str


class BackupJobListResponse(TypedDict):
    jobs: list[BackupJob]
    total: int


class AdminRealtimeEvent(TypedDict):
    event: str
    data: Any


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
