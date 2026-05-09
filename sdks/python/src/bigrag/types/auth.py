"""Authentication and session types."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class SetupStatusResponse(TypedDict):
    needs_setup: bool


class LoginBody(TypedDict):
    email: str
    password: str


class SetupBody(TypedDict):
    email: str
    password: str
    display_name: NotRequired[str]


class ChangePasswordBody(TypedDict):
    current_password: str
    new_password: str


class User(TypedDict):
    id: str
    email: str
    display_name: str
    role: str
    last_login_at: str | None
    created_at: str
    updated_at: str


class SessionResponse(TypedDict):
    user: User


class WhoamiResponse(TypedDict):
    authenticated: bool
    auth_method: str
    user_id: str
    user_email: str
    api_key_id: str | None
    api_key_name: str | None
    scopes: list[str] | None
    collection: str | None


class PreferencesResponse(TypedDict):
    data: dict[str, Any]
