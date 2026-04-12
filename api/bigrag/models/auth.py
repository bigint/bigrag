from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SetupStatusResponse(BaseModel):
    needs_setup: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)


class SetupRequest(BaseModel):
    email: EmailStr
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
    email: EmailStr
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


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    active: bool
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    expires_at: datetime | None = None


class CreateApiKeyResponse(ApiKeyResponse):
    key: str = Field(description="The plaintext API key (shown once).")


class UpdateApiKeyRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    active: bool | None = None


class ApiKeyListResponse(BaseModel):
    keys: list[ApiKeyResponse]
    total: int
