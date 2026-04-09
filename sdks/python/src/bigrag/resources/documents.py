"""Document operations resource."""

from __future__ import annotations

import json as _json
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import httpx

from bigrag._errors import error_for_status
from bigrag._files import FileInput, normalize_file_input
from bigrag._sse import parse_sse_stream
from bigrag._types import (
    BatchDeleteDocumentsResponse,
    BatchGetDocumentsResponse,
    BatchStatusResponse,
    Document,
    DocumentChunkListResponse,
    DocumentListResponse,
    ProgressEvent,
    StatusResponse,
)

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


class DocumentsResource:
    """Resource namespace for document operations within a collection.

    Access via ``client.documents``.
    """

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def upload(
        self,
        collection: str,
        file: FileInput,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        """Upload a single document to a collection."""
        name, data = normalize_file_input(file)
        files: dict[str, Any] = {"file": (name, data)}
        form_data: dict[str, Any] | None = None
        if metadata is not None:
            form_data = {"metadata": _json.dumps(metadata)}
        return await self._client._request_form(
            f"/v1/collections/{quote(collection, safe='')}/documents",
            files=files,
            data=form_data,
        )

    async def batch_upload(
        self,
        collection: str,
        files: list[FileInput],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentListResponse:
        """Upload multiple documents in a single request."""
        file_list: list[tuple[str, tuple[str, bytes | Any]]] = []
        for f in files:
            name, data = normalize_file_input(f)
            file_list.append(("files", (name, data)))
        form_data: dict[str, Any] | None = None
        if metadata is not None:
            form_data = {"metadata": _json.dumps(metadata)}
        return await self._client._request_form(
            f"/v1/collections/{quote(collection, safe='')}/documents/batch/upload",
            files=dict(file_list) if len(file_list) == 1 else file_list,  # type: ignore[arg-type]
            data=form_data,
        )

    async def list(
        self,
        collection: str,
        *,
        status: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> DocumentListResponse:
        """List documents in a collection with optional filtering and pagination."""
        params: dict[str, str] = {}
        if status is not None:
            params["status"] = status
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        return await self._client._request(
            "GET",
            f"/v1/collections/{quote(collection, safe='')}/documents",
            params=params,
        )

    async def get(self, collection: str, document_id: str) -> Document:
        """Retrieve a single document by ID."""
        return await self._client._request(
            "GET",
            f"/v1/collections/{quote(collection, safe='')}/documents/{quote(document_id, safe='')}",
        )

    async def delete(self, collection: str, document_id: str) -> StatusResponse:
        """Delete a document by ID."""
        return await self._client._request(
            "DELETE",
            f"/v1/collections/{quote(collection, safe='')}/documents/{quote(document_id, safe='')}",
        )

    async def reprocess(self, collection: str, document_id: str) -> StatusResponse:
        """Trigger reprocessing of a document."""
        return await self._client._request(
            "POST",
            f"/v1/collections/{quote(collection, safe='')}/documents/{quote(document_id, safe='')}/reprocess",
        )

    async def get_chunks(
        self, collection: str, document_id: str
    ) -> DocumentChunkListResponse:
        """Get all chunks for a document."""
        return await self._client._request(
            "GET",
            f"/v1/collections/{quote(collection, safe='')}/documents/{quote(document_id, safe='')}/chunks",
        )

    def get_file_url(self, collection: str, document_id: str) -> str:
        """Build the URL for downloading the original document file."""
        path = f"/v1/collections/{quote(collection, safe='')}/documents/{quote(document_id, safe='')}/file"
        if self._client.api_key:
            return f"{self._client.base_url}{path}?token={quote(self._client.api_key, safe='')}"
        return f"{self._client.base_url}{path}"

    async def batch_get_status(
        self, collection: str, document_ids: list[str]
    ) -> BatchStatusResponse:
        """Get the processing status of multiple documents at once."""
        return await self._client._request(
            "POST",
            f"/v1/collections/{quote(collection, safe='')}/documents/batch/status",
            json={"document_ids": document_ids},
        )

    async def batch_get(
        self, collection: str, document_ids: list[str]
    ) -> BatchGetDocumentsResponse:
        """Retrieve multiple documents at once."""
        return await self._client._request(
            "POST",
            f"/v1/collections/{quote(collection, safe='')}/documents/batch/get",
            json={"document_ids": document_ids},
        )

    async def batch_delete(
        self, collection: str, document_ids: list[str]
    ) -> BatchDeleteDocumentsResponse:
        """Delete multiple documents at once."""
        return await self._client._request(
            "POST",
            f"/v1/collections/{quote(collection, safe='')}/documents/batch/delete",
            json={"document_ids": document_ids},
        )

    async def ingest_s3(
        self,
        collection: str,
        *,
        bucket: str,
        prefix: str = "",
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """List objects in an S3 bucket and ingest supported files."""
        body: dict[str, Any] = {
            "bucket": bucket,
            "prefix": prefix,
            "region": region,
        }
        if endpoint_url is not None:
            body["endpoint_url"] = endpoint_url
        if access_key is not None:
            body["access_key"] = access_key
        if secret_key is not None:
            body["secret_key"] = secret_key
        if metadata is not None:
            body["metadata"] = metadata
        return await self._client._request(
            "POST",
            f"/v1/collections/{quote(collection, safe='')}/documents/s3",
            json=body,
        )

    async def stream_batch_progress(
        self, collection: str, document_ids: list[str]
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Stream aggregated progress for multiple documents via SSE."""
        ids_param = ",".join(document_ids)
        path = f"/v1/collections/{quote(collection, safe='')}/documents/batch/progress"
        token_param = (
            f"&token={quote(self._client.api_key, safe='')}"
            if self._client.api_key
            else ""
        )
        url = f"{self._client.base_url}{path}?ids={quote(ids_param, safe='')}{token_param}"

        request = self._client._client.build_request(
            "GET",
            url,
            headers={"User-Agent": "bigrag-python/0.1.0"},
        )
        response = await self._client._client.send(request, stream=True)

        if response.status_code >= 400:
            await response.aread()
            raise error_for_status(response.status_code, response.reason_phrase or "Unknown error")

        async for event in parse_sse_stream(response):
            yield event

    async def stream_progress(
        self, collection: str, document_id: str
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Stream real-time processing progress for a document via SSE."""
        path = (
            f"/v1/collections/{quote(collection, safe='')}"
            f"/documents/{quote(document_id, safe='')}/progress"
        )
        token_param = (
            f"?token={quote(self._client.api_key, safe='')}"
            if self._client.api_key
            else ""
        )
        url = f"{self._client.base_url}{path}{token_param}"

        request = self._client._client.build_request(
            "GET",
            url,
            headers={"User-Agent": "bigrag-python/0.1.0"},
        )
        response = await self._client._client.send(request, stream=True)

        if response.status_code >= 400:
            await response.aread()
            raise error_for_status(response.status_code, response.reason_phrase or "Unknown error")

        async for event in parse_sse_stream(response):
            yield event
