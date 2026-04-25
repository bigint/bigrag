from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field

# Pragmatic email validator for self-hosted deployments. Pydantic's EmailStr
# rejects reserved TLDs like `.local`, `.internal`, `.corp`, breaking on-prem
# Active Directory shops. We validate basic RFC 5322 shape and length — DNS
# deliverability is the operator's concern, not ours.
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


class SessionResponse(BaseModel):
    user: UserResponse


class CreateUserRequest(BaseModel):
    email: PermissiveEmail
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(default="", max_length=120)
    role: str = Field(default="admin", pattern="^(admin|member)$")


class UpdateUserRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, pattern="^(admin|member)$")
    password: str | None = Field(default=None, min_length=8, max_length=256)


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


class ApiKeyScope(BaseModel):
    """A granular permission. Scopes resolve to ``resource:action``
    strings (e.g. ``collection:read``, ``document:upload``). Wildcards
    allowed: ``*:read``, ``collection:*``, ``*:*``.
    """

    resource: str = Field(min_length=1, max_length=40)
    action: str = Field(min_length=1, max_length=40)


VALID_RESOURCES = frozenset(
    {"*", "collection", "document", "query", "webhook", "api_key", "user", "audit"}
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
    rate_limits: dict | None = None
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
            "List of 'resource:action' strings. Omit for a legacy "
            "full-access key. Examples: ['collection:read', "
            "'document:upload'] — or ['*:*'] for unrestricted."
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
    rate_limits: dict | None = Field(
        default=None,
        description=(
            "Optional per-bucket overrides, e.g. {'POST:/v1/query': 300, 'POST:/v1/documents': 30}."
        ),
    )


class CreateApiKeyResponse(ApiKeyResponse):
    key: str = Field(description="The plaintext API key (shown once).")


class UpdateApiKeyRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    active: bool | None = None
    scopes: list[str] | None = None
    collection: str | None = Field(
        default=None,
        max_length=80,
        description="Empty string clears the scope; a name pins to that collection.",
    )
    rate_limits: dict | None = None


class WhoamiResponse(BaseModel):
    """Returned by /v1/auth/whoami so clients (including the MCP server)
    can discover what they're authenticated as and what scope they have.
    """

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
    total: int


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
    total: int
