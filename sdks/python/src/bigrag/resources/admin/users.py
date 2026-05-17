from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag.resources.admin._shared import _pagination
from bigrag.types.admin import CreateUserBody, UpdateUserBody, UserListResponse
from bigrag.types.auth import User
from bigrag.types.common import StatusResponse

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminUsersResource:

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> UserListResponse:
        params = _pagination(limit=limit, offset=offset)
        return await self._client._request("GET", "/v1/admin/users", params=params)

    async def create(self, body: CreateUserBody) -> User:
        return await self._client._request("POST", "/v1/admin/users", json=body)

    async def update(self, user_id: str, body: UpdateUserBody) -> User:
        return await self._client._request(
            "PATCH", f"/v1/admin/users/{quote(user_id, safe='')}", json=body
        )

    async def delete(self, user_id: str) -> StatusResponse:
        return await self._client._request(
            "DELETE", f"/v1/admin/users/{quote(user_id, safe='')}"
        )
