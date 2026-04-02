from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class SetupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


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
    collections: list[str] = []
    operations: list[str] = []
    admin: bool = False
    expires_at: datetime | None = None
