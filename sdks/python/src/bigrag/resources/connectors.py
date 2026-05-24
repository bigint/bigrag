from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from bigrag.types.common import StatusResponse
from bigrag.types.connectors import (
    CreateS3SourceBody,
    S3Source,
    S3SourceListResponse,
    S3SyncJob,
    S3SyncJobListResponse,
    UpdateS3SourceBody,
)

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class ConnectorsResource:
    s3: S3ConnectorResource

    def __init__(self, client: BigRAGCore) -> None:
        self.s3 = S3ConnectorResource(client)


class S3ConnectorResource:
    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def sources(self, *, collection: str | None = None) -> S3SourceListResponse:
        params: dict[str, str] = {}
        if collection is not None:
            params["collection"] = collection
        return await self._client._request("GET", "/v1/connectors/s3/sources", params=params)

    async def create_source(self, body: CreateS3SourceBody) -> S3Source:
        return await self._client._request("POST", "/v1/connectors/s3/sources", json=body)

    async def update_source(self, source_id: str, body: UpdateS3SourceBody) -> S3Source:
        return await self._client._request(
            "PATCH",
            f"/v1/connectors/s3/sources/{quote(source_id, safe='')}",
            json=body,
        )

    async def delete_source(self, source_id: str) -> StatusResponse:
        return await self._client._request(
            "DELETE", f"/v1/connectors/s3/sources/{quote(source_id, safe='')}"
        )

    async def sync_source(self, source_id: str) -> S3SyncJob:
        return await self._client._request(
            "POST", f"/v1/connectors/s3/sources/{quote(source_id, safe='')}/sync"
        )

    async def sync_jobs(
        self,
        *,
        collection: str | None = None,
        source_id: str | None = None,
        limit: int | None = None,
    ) -> S3SyncJobListResponse:
        params: dict[str, str] = {}
        if collection is not None:
            params["collection"] = collection
        if source_id is not None:
            params["source_id"] = source_id
        if limit is not None:
            params["limit"] = str(limit)
        return await self._client._request("GET", "/v1/connectors/s3/sync-jobs", params=params)
