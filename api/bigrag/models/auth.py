from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, BeforeValidator, Field

if TYPE_CHECKING:
    from bigrag.db.models import User

_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?)+$"
)


def _normalize_email(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("email must be a string")
    candidate = value.strip().lower()
    if len(candidate) > 254 or not _EMAIL_RE.match(candidate):
        raise ValueError("value is not a valid email address")
    local, _, domain = candidate.partition("@")
    if len(local) > 64 or len(domain) > 253:
        raise ValueError("value is not a valid email address")
    return candidate


PermissiveEmail = Annotated[str, BeforeValidator(_normalize_email)]


class SetupStatusResponse(BaseModel):
    needs_setup: bool


class LoginRequest(BaseModel):
    email: PermissiveEmail
    password: str = Field(min_length=8, max_length=256)


class SetupRequest(BaseModel):
    email: PermissiveEmail
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(default="", max_length=120)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_user(cls, user: User) -> UserResponse:
        return cls(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class SessionResponse(BaseModel):
    user: UserResponse


class CreateUserRequest(BaseModel):
    email: PermissiveEmail
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(default="", max_length=120)
    role: str = Field(default="admin", pattern="^(admin|member)$")


class UpdateUserRequest(BaseModel):
    email: PermissiveEmail | None = Field(default=None)
    display_name: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, pattern="^(admin|member)$")
    password: str | None = Field(default=None, min_length=8, max_length=256)


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int | None = None
    next_cursor: str | None = None


VALID_RESOURCES = frozenset(
    {
        "*",
        "collection",
        "document",
        "query",
        "chat",
        "webhook",
        "api_key",
        "user",
        "audit",
        "vector",
    }
)
VALID_ACTIONS = frozenset({"*", "read", "write", "upload", "delete", "admin"})


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    active: bool
    scopes: list[str] = Field(default_factory=list)
    collection: str | None = Field(
        default=None,
        description=(
            "When set, this key can only see/query this one collection. "
            "Cross-collection endpoints return 403."
        ),
    )
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    expires_at: datetime | None = None
    scopes: list[str] | None = Field(
        default=None,
        description=(
            "List of 'resource:action' strings. Omit or pass [] to "
            "store ['*:*'] for a full-access key. Examples: "
            "['collection:read', 'document:upload']."
        ),
    )
    collection: str | None = Field(
        default=None,
        max_length=80,
        description=(
            "Pin the key to a single collection. Cross-collection "
            "endpoints return 403 when this is set."
        ),
    )


class CreateApiKeyResponse(ApiKeyResponse):
    key: str = Field(description="The plaintext API key (shown once).")


class UpdateApiKeyRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    active: bool | None = None
    expires_at: datetime | None = None
    scopes: list[str] | None = None
    collection: str | None = Field(
        default=None,
        max_length=80,
        description="Empty string clears the scope; a name pins to that collection.",
    )


class WhoamiResponse(BaseModel):
    authenticated: bool = True
    auth_method: str = Field(description="'session' or 'api_key'")
    user_id: str
    user_email: str
    api_key_id: str | None = None
    api_key_name: str | None = None
    scopes: list[str] | None = None
    collection: str | None = Field(
        default=None,
        description="Collection the key is pinned to, or null for full-workspace access.",
    )


class ApiKeyListResponse(BaseModel):
    keys: list[ApiKeyResponse]
    total: int | None = None
    next_cursor: str | None = None


class AuditLogEntry(BaseModel):
    id: str
    actor_id: str | None = None
    actor_email: str | None = None
    api_key_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    metadata: dict
    ip: str | None = None
    user_agent: str | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    entries: list[AuditLogEntry]
    total: int | None = None
    next_cursor: str | None = None
