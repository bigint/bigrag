"""Connector resources."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from rag_computer.types.common import StatusResponse
from rag_computer.types.connectors import (
    CreateGoogleSourceBody,
    GoogleAccount,
    GoogleDriveFileListResponse,
    GoogleOAuthStartUrlResponse,
    GoogleSource,
    GoogleSourceListResponse,
    GoogleSyncJob,
    GoogleSyncJobListResponse,
    UpdateGoogleSourceBody,
)

if TYPE_CHECKING:
    from rag_computer._core import RagComputerCore


class ConnectorsResource:
    """Container for user connector resources."""

    google: GoogleDriveResource

    def __init__(self, client: RagComputerCore) -> None:
        self.google = GoogleDriveResource(client)


class GoogleDriveResource:
    """Google Drive connector resource."""

    def __init__(self, client: RagComputerCore) -> None:
        self._client = client

    async def account(self) -> GoogleAccount:
        """Get the current user's Google Drive account status."""
        return await self._client._request("GET", "/v1/connectors/google/account")

    async def files(
        self,
        *,
        parent_id: str = "root",
        query: str | None = None,
        page_token: str | None = None,
        page_size: int | None = None,
    ) -> GoogleDriveFileListResponse:
        """List Google Drive files visible to the current user."""
        params: dict[str, str] = {"parent_id": parent_id}
        if query is not None:
            params["query"] = query
        if page_token is not None:
            params["page_token"] = page_token
        if page_size is not None:
            params["page_size"] = str(page_size)
        return await self._client._request(
            "GET", "/v1/connectors/google/files", params=params
        )

    async def oauth_start_url(
        self, *, redirect_path: str | None = None
    ) -> GoogleOAuthStartUrlResponse:
        """Build a Google OAuth URL for the current user."""
        params: dict[str, str] = {}
        if redirect_path is not None:
            params["redirect_path"] = redirect_path
        return await self._client._request(
            "GET",
            "/v1/connectors/google/oauth/start-url",
            params=params,
        )

    async def disconnect(self) -> StatusResponse:
        """Disconnect the current user's Google Drive account."""
        return await self._client._request("POST", "/v1/connectors/google/disconnect")

    async def sources(
        self, *, collection: str | None = None
    ) -> GoogleSourceListResponse:
        """List Google Drive sync sources."""
        params: dict[str, str] = {}
        if collection is not None:
            params["collection"] = collection
        return await self._client._request(
            "GET", "/v1/connectors/google/sources", params=params
        )

    async def create_source(self, body: CreateGoogleSourceBody) -> GoogleSource:
        """Create a Google Drive sync source."""
        return await self._client._request(
            "POST", "/v1/connectors/google/sources", json=body
        )

    async def update_source(
        self, source_id: str, body: UpdateGoogleSourceBody
    ) -> GoogleSource:
        """Update a Google Drive sync source."""
        return await self._client._request(
            "PATCH",
            f"/v1/connectors/google/sources/{quote(source_id, safe='')}",
            json=body,
        )

    async def delete_source(self, source_id: str) -> StatusResponse:
        """Delete a Google Drive sync source."""
        return await self._client._request(
            "DELETE", f"/v1/connectors/google/sources/{quote(source_id, safe='')}"
        )

    async def sync_source(self, source_id: str) -> GoogleSyncJob:
        """Trigger an immediate sync for a Google Drive source."""
        return await self._client._request(
            "POST", f"/v1/connectors/google/sources/{quote(source_id, safe='')}/sync"
        )

    async def sync_jobs(
        self,
        *,
        collection: str | None = None,
        source_id: str | None = None,
        limit: int | None = None,
    ) -> GoogleSyncJobListResponse:
        """List Google Drive sync jobs."""
        params: dict[str, str] = {}
        if collection is not None:
            params["collection"] = collection
        if source_id is not None:
            params["source_id"] = source_id
        if limit is not None:
            params["limit"] = str(limit)
        return await self._client._request(
            "GET", "/v1/connectors/google/sync-jobs", params=params
        )
