from __future__ import annotations

from typing import TYPE_CHECKING, Any
from bigrag.types.auth import (
    ChangePasswordBody,
    LoginBody,
    PreferencesResponse,
    SessionResponse,
    SetupBody,
    SetupStatusResponse,
    WhoamiResponse,
)
from bigrag.types.common import StatusResponse

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AuthResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def setup_status(self) -> SetupStatusResponse:
        return await self._client._request("GET", "/v1/auth/setup-status")

    async def setup(self, body: SetupBody) -> SessionResponse:
        return await self._client._request("POST", "/v1/auth/setup", json=body)

    async def login(self, body: LoginBody) -> SessionResponse:
        return await self._client._request("POST", "/v1/auth/login", json=body)

    async def logout(self) -> StatusResponse:
        return await self._client._request("POST", "/v1/auth/logout")

    async def logout_all(self) -> StatusResponse:
        return await self._client._request("POST", "/v1/auth/logout-all")

    async def me(self) -> SessionResponse:
        return await self._client._request("GET", "/v1/auth/me")

    async def whoami(self) -> WhoamiResponse:
        return await self._client._request("GET", "/v1/auth/whoami")

    async def change_password(self, body: ChangePasswordBody) -> StatusResponse:
        return await self._client._request("POST", "/v1/auth/password", json=body)

    async def get_preferences(self) -> PreferencesResponse:
        return await self._client._request("GET", "/v1/auth/preferences")

    async def update_preferences(self, data: dict[str, Any]) -> PreferencesResponse:
        return await self._client._request(
            "PUT", "/v1/auth/preferences", json={"data": data}
        )
