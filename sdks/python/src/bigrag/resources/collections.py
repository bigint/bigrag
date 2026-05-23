from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag._errors import error_for_status
from bigrag._sse import parse_sse_stream
from bigrag.types.analytics import AnalyticsResponse
from bigrag.types.collections import (
    Collection,
    CollectionEventTokenResponse,
    CollectionListResponse,
    CollectionStatsResponse,
    CreateCollectionBody,
    UpdateCollectionBody,
)
from bigrag.types.common import StatusResponse
from bigrag.types.sse import ProgressEvent

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class CollectionsResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def list(
        self,
        *,
        name: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> CollectionListResponse:
        params: dict[str, str] = {}
        if name is not None:
            params["name"] = name
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        return await self._client._request("GET", "/v1/collections", params=params)

    async def get(self, name: str) -> Collection:
        return await self._client._request(
            "GET", f"/v1/collections/{quote(name, safe='')}"
        )

    async def create(self, body: CreateCollectionBody) -> Collection:
        return await self._client._request("POST", "/v1/collections", json=body)

    async def update(self, name: str, body: UpdateCollectionBody) -> Collection:
        return await self._client._request(
            "PUT", f"/v1/collections/{quote(name, safe='')}", json=body
        )

    async def delete(self, name: str) -> StatusResponse:
        return await self._client._request(
            "DELETE", f"/v1/collections/{quote(name, safe='')}"
        )

    async def stats(self, name: str) -> CollectionStatsResponse:
        return await self._client._request(
            "GET", f"/v1/collections/{quote(name, safe='')}/stats"
        )

    async def analytics(self, name: str) -> AnalyticsResponse:
        return await self._client._request(
            "GET", f"/v1/collections/{quote(name, safe='')}/analytics"
        )

    async def truncate(self, name: str) -> StatusResponse:
        return await self._client._request(
            "POST", f"/v1/collections/{quote(name, safe='')}/truncate"
        )

    async def create_event_token(self, name: str) -> CollectionEventTokenResponse:
        return await self._client._request(
            "POST", f"/v1/collections/{quote(name, safe='')}/events/token"
        )

    async def stream_events(
        self, name: str, *, token: str | None = None
    ) -> AsyncGenerator[ProgressEvent, None]:
        path = f"/v1/collections/{quote(name, safe='')}/events"
        url = f"{self._client.base_url}{path}"
        params = {"token": token} if token is not None else None
        async with self._client._client.stream(
            "GET",
            url,
            params=params,
            headers=self._client._headers(),
        ) as response:
            if response.status_code >= 400:
                await response.aread()
                raise error_for_status(
                    response.status_code,
                    response.reason_phrase or "Unknown error",
                )
            async for event in parse_sse_stream(response):
                yield event
