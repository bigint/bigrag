"""Authentication and session resource."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from rag_computer.types.auth import (
    ChangePasswordBody,
    LoginBody,
    PreferencesResponse,
    SessionResponse,
    SetupBody,
    SetupStatusResponse,
    WhoamiResponse,
)
from rag_computer.types.common import StatusResponse

if TYPE_CHECKING:
    from rag_computer._core import RagComputerCore


class AuthResource:
    """Resource namespace for session auth and user preferences.

    Session endpoints use the underlying ``httpx`` cookie jar, so a successful
    ``login`` or ``setup`` call authenticates subsequent session-only requests
    made by the same client instance.
    """

    def __init__(self, client: RagComputerCore) -> None:
        self._client = client

    async def setup_status(self) -> SetupStatusResponse:
        """Return whether the server still needs first-run admin setup."""
        return await self._client._request("GET", "/v1/auth/setup-status")

    async def setup(self, body: SetupBody) -> SessionResponse:
        """Create the first admin account and start a session."""
        return await self._client._request("POST", "/v1/auth/setup", json=body)

    async def login(self, body: LoginBody) -> SessionResponse:
        """Start a browser-style session using email and password."""
        return await self._client._request("POST", "/v1/auth/login", json=body)

    async def logout(self) -> StatusResponse:
        """Revoke the current session."""
        return await self._client._request("POST", "/v1/auth/logout")

    async def logout_all(self) -> StatusResponse:
        """Revoke all sessions for the current user."""
        return await self._client._request("POST", "/v1/auth/logout-all")

    async def me(self) -> SessionResponse:
        """Return the current session user."""
        return await self._client._request("GET", "/v1/auth/me")

    async def whoami(self) -> WhoamiResponse:
        """Return the current principal, including API key scope details."""
        return await self._client._request("GET", "/v1/auth/whoami")

    async def change_password(self, body: ChangePasswordBody) -> StatusResponse:
        """Change the current session user's password."""
        return await self._client._request("POST", "/v1/auth/password", json=body)

    async def get_preferences(self) -> PreferencesResponse:
        """Return the current user's admin UI preferences."""
        return await self._client._request("GET", "/v1/auth/preferences")

    async def update_preferences(self, data: dict[str, Any]) -> PreferencesResponse:
        """Merge admin UI preferences for the current user."""
        return await self._client._request(
            "PUT", "/v1/auth/preferences", json={"data": data}
        )
