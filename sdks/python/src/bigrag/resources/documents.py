"""Document operations resource."""

from __future__ import annotations

import json as _json
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from bigrag._errors import error_for_status
from bigrag._files import FileInput, normalize_file_input
from bigrag._sse import parse_sse_stream
from bigrag.types.common import StatusResponse
from bigrag.types.documents import (
    BatchDeleteDocumentsResponse,
    BatchGetDocumentsResponse,
    BatchStatusResponse,
    Document,
    DocumentChunkListResponse,
    DocumentListResponse,
)
from bigrag.types.sse import ProgressEvent

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore

_UA = "bigrag-python/0.0.1"


def _col_path(collection: str) -> str:
    return f"/v1/collections/{quote(collection, safe='')}"


def _doc_path(collection: str, document_id: str) -> str:
    return (
        f"{_col_path(collection)}"
        f"/documents/{quote(document_id, safe='')}"
    )


class DocumentsResource:
    """Resource namespace for document operations.

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
            f"{_col_path(collection)}/documents",
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
            f"{_col_path(collection)}/documents/batch/upload",
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
        """List documents in a collection."""
        params: dict[str, str] = {}
        if status is not None:
            params["status"] = status
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        return await self._client._request(
            "GET", f"{_col_path(collection)}/documents", params=params,
        )

    async def get(self, collection: str, document_id: str) -> Document:
        """Retrieve a document by ID within a collection."""
        return await self._client._request("GET", _doc_path(collection, document_id))

    async def get_by_id(self, document_id: str) -> Document:
        """Retrieve a document by ID (without specifying collection)."""
        return await self._client._request(
            "GET", f"/v1/documents/{quote(document_id, safe='')}",
        )

    async def delete(self, collection: str, document_id: str) -> StatusResponse:
        """Delete a document by ID."""
        return await self._client._request("DELETE", _doc_path(collection, document_id))

    async def reprocess(self, collection: str, document_id: str) -> StatusResponse:
        """Trigger reprocessing of a document."""
        return await self._client._request(
            "POST", f"{_doc_path(collection, document_id)}/reprocess",
        )

    async def get_chunks(
        self, collection: str, document_id: str,
    ) -> DocumentChunkListResponse:
        """Get all chunks for a document within a collection."""
        return await self._client._request(
            "GET", f"{_doc_path(collection, document_id)}/chunks",
        )

    async def get_chunks_by_id(
        self, document_id: str,
    ) -> DocumentChunkListResponse:
        """Get chunks for a document by ID (without specifying collection)."""
        return await self._client._request(
            "GET", f"/v1/documents/{quote(document_id, safe='')}/chunks",
        )

    def get_file_url(self, collection: str, document_id: str) -> str:
        """Build the URL for downloading the original document file."""
        path = f"{_doc_path(collection, document_id)}/file"
        if self._client.api_key:
            return (
                f"{self._client.base_url}{path}"
                f"?token={quote(self._client.api_key, safe='')}"
            )
        return f"{self._client.base_url}{path}"

    async def batch_get_status(
        self, collection: str, document_ids: list[str],
    ) -> BatchStatusResponse:
        """Get the processing status of multiple documents."""
        return await self._client._request(
            "POST",
            f"{_col_path(collection)}/documents/batch/status",
            json={"document_ids": document_ids},
        )

    async def batch_get(
        self, collection: str, document_ids: list[str],
    ) -> BatchGetDocumentsResponse:
        """Retrieve multiple documents at once."""
        return await self._client._request(
            "POST",
            f"{_col_path(collection)}/documents/batch/get",
            json={"document_ids": document_ids},
        )

    async def batch_delete(
        self, collection: str, document_ids: list[str],
    ) -> BatchDeleteDocumentsResponse:
        """Delete multiple documents at once."""
        return await self._client._request(
            "POST",
            f"{_col_path(collection)}/documents/batch/delete",
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
        no_sign_request: bool = False,
        file_types: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Ingest files from an S3 bucket."""
        body: dict[str, Any] = {
            "bucket": bucket, "prefix": prefix, "region": region,
        }
        if endpoint_url is not None:
            body["endpoint_url"] = endpoint_url
        if access_key is not None:
            body["access_key"] = access_key
        if secret_key is not None:
            body["secret_key"] = secret_key
        if no_sign_request:
            body["no_sign_request"] = True
        if file_types:
            body["file_types"] = file_types
        if metadata is not None:
            body["metadata"] = metadata
        return await self._client._request(
            "POST", f"{_col_path(collection)}/documents/s3", json=body,
        )

    async def list_s3_jobs(self, collection: str) -> Any:
        """List S3 ingest jobs for a collection."""
        return await self._client._request(
            "GET", f"{_col_path(collection)}/s3-jobs",
        )

    async def delete_s3_job(self, collection: str, job_id: str) -> Any:
        """Delete an S3 ingest job."""
        return await self._client._request(
            "DELETE",
            f"{_col_path(collection)}/s3-jobs/{quote(job_id, safe='')}",
        )

    async def resync_s3_job(self, collection: str, job_id: str) -> Any:
        """Re-sync an S3 ingest job."""
        return await self._client._request(
            "POST",
            f"{_col_path(collection)}/s3-jobs/{quote(job_id, safe='')}/resync",
        )

    async def stream_batch_progress(
        self, collection: str, document_ids: list[str],
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Stream aggregated progress for multiple documents via SSE."""
        ids_param = ",".join(document_ids)
        path = f"{_col_path(collection)}/documents/batch/progress"
        token = (
            f"&token={quote(self._client.api_key, safe='')}"
            if self._client.api_key else ""
        )
        url = f"{self._client.base_url}{path}?ids={quote(ids_param, safe='')}{token}"
        async for event in self._stream_sse(url):
            yield event

    async def stream_progress(
        self, collection: str, document_id: str,
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Stream real-time processing progress for a document."""
        path = f"{_doc_path(collection, document_id)}/progress"
        token = (
            f"?token={quote(self._client.api_key, safe='')}"
            if self._client.api_key else ""
        )
        url = f"{self._client.base_url}{path}{token}"
        async for event in self._stream_sse(url):
            yield event

    async def _stream_sse(
        self, url: str,
    ) -> AsyncGenerator[ProgressEvent, None]:
        """Internal helper to stream SSE from a URL."""
        request = self._client._client.build_request(
            "GET", url, headers={"User-Agent": _UA},
        )
        response = await self._client._client.send(request, stream=True)
        if response.status_code >= 400:
            await response.aread()
            raise error_for_status(
                response.status_code,
                response.reason_phrase or "Unknown error",
            )
        async for event in parse_sse_stream(response):
            yield event
