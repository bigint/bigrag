from __future__ import annotations

from typing import TYPE_CHECKING

from bigrag.resources.admin._shared import _pagination
from bigrag.types.access import AccessLogListResponse, AccessLogOverviewResponse

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class AdminAccessResource:

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def logs(
        self,
        *,
        action: str | None = None,
        actor_id: str | None = None,
        collection: str | None = None,
        method: str | None = None,
        path: str | None = None,
        status_family: str | None = None,
        success: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> AccessLogListResponse:
        params = _pagination(limit=limit, offset=offset)
        if action is not None:
            params["action"] = action
        if actor_id is not None:
            params["actor_id"] = actor_id
        if collection is not None:
            params["collection"] = collection
        if method is not None:
            params["method"] = method
        if path is not None:
            params["path"] = path
        if status_family is not None:
            params["status_family"] = status_family
        if success is not None:
            params["success"] = "true" if success else "false"
        return await self._client._request(
            "GET", "/v1/admin/access/logs", params=params
        )

    async def overview(
        self, *, window_days: int | None = None
    ) -> AccessLogOverviewResponse:
        params: dict[str, str] = {}
        if window_days is not None:
            params["window_days"] = str(window_days)
        return await self._client._request(
            "GET", "/v1/admin/access/overview", params=params
        )
