from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class SetupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1)
    invite_code: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    created_at: datetime
    updated_at: datetime


class AuthResponse(BaseModel):
    token: str
    user: UserResponse


class CreateApiKeyRequest(BaseModel):
    name: str
    namespaces: list[str] = []
    operations: list[str] = []
    admin: bool = False
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    key: str | None = None
    permissions: dict
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime | None = None


class CreateInviteRequest(BaseModel):
    role: str = "member"
    expires_in_hours: int = 72


class InviteResponse(BaseModel):
    id: str
    code: str
    role: str
    expires_at: datetime
    created_at: datetime
    used_by: str | None = None
    created_by_email: str | None = None


class UpdateRoleRequest(BaseModel):
    role: str = Field(pattern="^(admin|member)$")
