from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag._realtime import RealtimeConnection
from bigrag.types.analytics import AnalyticsResponse
from bigrag.types.collections import (
    Collection,
    CollectionListResponse,
    CollectionRealtimeTokenResponse,
    CollectionStatsResponse,
    CreateCollectionBody,
    UpdateCollectionBody,
)
from bigrag.types.common import StatusResponse
from bigrag.types.realtime import ProgressEvent

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
        return await self._client._request("GET", f"/v1/collections/{quote(name, safe='')}")

    async def create(self, body: CreateCollectionBody) -> Collection:
        return await self._client._request("POST", "/v1/collections", json=body)

    async def update(self, name: str, body: UpdateCollectionBody) -> Collection:
        return await self._client._request(
            "PUT", f"/v1/collections/{quote(name, safe='')}", json=body
        )

    async def delete(self, name: str) -> StatusResponse:
        return await self._client._request("DELETE", f"/v1/collections/{quote(name, safe='')}")

    async def stats(self, name: str) -> CollectionStatsResponse:
        return await self._client._request("GET", f"/v1/collections/{quote(name, safe='')}/stats")

    async def analytics(self, name: str) -> AnalyticsResponse:
        return await self._client._request(
            "GET", f"/v1/collections/{quote(name, safe='')}/analytics"
        )

    async def truncate(self, name: str) -> StatusResponse:
        return await self._client._request(
            "POST", f"/v1/collections/{quote(name, safe='')}/truncate"
        )

    async def create_realtime_token(self, name: str) -> CollectionRealtimeTokenResponse:
        return await self._client._request(
            "POST", f"/v1/collections/{quote(name, safe='')}/realtime-token"
        )

    async def stream_events(
        self, name: str, *, token: str | None = None
    ) -> AsyncGenerator[ProgressEvent, None]:
        connection = RealtimeConnection(self._client)
        try:
            async for message in connection.subscribe(
                "collection.events", {"collection": name, "token": token}
            ):
                if message["type"] == "event":
                    yield message["payload"]
                elif message["type"] == "error":
                    raise RuntimeError(message["message"])
                elif message["type"] == "complete":
                    return
        finally:
            await connection.close()
