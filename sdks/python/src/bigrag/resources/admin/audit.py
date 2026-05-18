from __future__ import annotations

from typing import TYPE_CHECKING

from bigrag.resources.admin._shared import _pagination
from bigrag.types.admin import AuditLogListResponse

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminAuditResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(
        self,
        *,
        action: str | None = None,
        actor_id: str | None = None,
        resource_type: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> AuditLogListResponse:
        params = _pagination(limit=limit, offset=offset)
        if action is not None:
            params["action"] = action
        if actor_id is not None:
            params["actor_id"] = actor_id
        if resource_type is not None:
            params["resource_type"] = resource_type
        return await self._client._request("GET", "/v1/admin/audit", params=params)
