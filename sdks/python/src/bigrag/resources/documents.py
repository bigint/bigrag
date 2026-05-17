from __future__ import annotations

import json as _json
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from bigrag._files import FileInput, normalize_file_input
from bigrag.types.common import StatusResponse
from bigrag.types.documents import (
    BatchDeleteDocumentsResponse,
    BatchGetDocumentsResponse,
    BatchStatusResponse,
    Document,
    DocumentChunkListResponse,
    DocumentListResponse,
    UploadSession,
    UploadSessionFileResponse,
)

if TYPE_CHECKING:
    from bigrag._core import BigRAGCore


def _col_path(collection: str) -> str:
    return f"/v1/collections/{quote(collection, safe='')}"


def _doc_path(collection: str, document_id: str) -> str:
    return f"{_col_path(collection)}/documents/{quote(document_id, safe='')}"


def _upload_session_path(collection: str, session_id: str | None = None) -> str:
    base = f"{_col_path(collection)}/upload-sessions"
    return base if session_id is None else f"{base}/{quote(session_id, safe='')}"


class DocumentsResource:

    def __init__(self, client: BigRAGCore) -> None:
        self._client = client

    async def upload(
        self,
        collection: str,
        file: FileInput,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Document:
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
        file_list: list[tuple[str, tuple[str, bytes | Any]]] = []
        for f in files:
            name, data = normalize_file_input(f)
            file_list.append(("files", (name, data)))
        form_data: dict[str, Any] | None = None
        if metadata is not None:
            form_data = {"metadata": _json.dumps(metadata)}
        return await self._client._request_form(
            f"{_col_path(collection)}/documents/batch/upload",
            files=file_list,
            data=form_data,
        )

    async def create_upload_session(
        self,
        collection: str,
        *,
        total_files: int,
        total_bytes: int,
        metadata: dict[str, Any] | None = None,
    ) -> UploadSession:
        return await self._client._request(
            "POST",
            _upload_session_path(collection),
            json={
                "total_files": total_files,
                "total_bytes": total_bytes,
                "metadata": metadata or {},
            },
        )

    async def get_upload_session(
        self, collection: str, session_id: str
    ) -> UploadSession:
        return await self._client._request(
            "GET",
            _upload_session_path(collection, session_id),
        )

    async def upload_session_file(
        self,
        collection: str,
        session_id: str,
        file: FileInput,
        *,
        client_item_id: str | None = None,
        filename: str | None = None,
    ) -> UploadSessionFileResponse:
        name, data = normalize_file_input(file)
        form_data = (
            {"client_item_id": client_item_id} if client_item_id is not None else None
        )
        return await self._client._request_form(
            f"{_upload_session_path(collection, session_id)}/files",
            files={"file": (filename or name, data)},
            data=form_data,
        )

    async def complete_upload_session(
        self, collection: str, session_id: str
    ) -> UploadSession:
        return await self._client._request(
            "POST",
            f"{_upload_session_path(collection, session_id)}/complete",
        )

    async def cancel_upload_session(
        self, collection: str, session_id: str
    ) -> StatusResponse:
        return await self._client._request(
            "POST",
            f"{_upload_session_path(collection, session_id)}/cancel",
        )

    async def list(
        self,
        collection: str,
        *,
        q: str | None = None,
        status: str | None = None,
        sort: str | None = None,
        order: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_total: bool | None = None,
    ) -> DocumentListResponse:
        params: dict[str, str] = {}
        if q is not None:
            params["q"] = q
        if status is not None:
            params["status"] = status
        if sort is not None:
            params["sort"] = sort
        if order is not None:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        if include_total is not None:
            params["include_total"] = "true" if include_total else "false"
        return await self._client._request(
            "GET",
            f"{_col_path(collection)}/documents",
            params=params,
        )

    async def get(self, collection: str, document_id: str) -> Document:
        return await self._client._request("GET", _doc_path(collection, document_id))

    async def get_by_id(self, document_id: str) -> Document:
        return await self._client._request(
            "GET",
            f"/v1/documents/{quote(document_id, safe='')}",
        )

    async def delete(self, collection: str, document_id: str) -> StatusResponse:
        return await self._client._request("DELETE", _doc_path(collection, document_id))

    async def reprocess(self, collection: str, document_id: str) -> StatusResponse:
        return await self._client._request(
            "POST",
            f"{_doc_path(collection, document_id)}/reprocess",
        )

    async def get_chunks(
        self,
        collection: str,
        document_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> DocumentChunkListResponse:
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        return await self._client._request(
            "GET",
            f"{_doc_path(collection, document_id)}/chunks",
            params=params,
        )

    async def get_chunks_by_id(
        self,
        document_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> DocumentChunkListResponse:
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if offset is not None:
            params["offset"] = str(offset)
        return await self._client._request(
            "GET",
            f"/v1/documents/{quote(document_id, safe='')}/chunks",
            params=params,
        )

    def get_file_url(self, collection: str, document_id: str) -> str:
        path = f"{_doc_path(collection, document_id)}/file"
        return f"{self._client.base_url}{path}"

    async def batch_get_status(
        self,
        collection: str,
        document_ids: list[str],
    ) -> BatchStatusResponse:
        return await self._client._request(
            "POST",
            f"{_col_path(collection)}/documents/batch/status",
            json={"document_ids": document_ids},
        )

    async def batch_get(
        self,
        collection: str,
        document_ids: list[str],
    ) -> BatchGetDocumentsResponse:
        return await self._client._request(
            "POST",
            f"{_col_path(collection)}/documents/batch/get",
            json={"document_ids": document_ids},
        )

    async def batch_delete(
        self,
        collection: str,
        document_ids: list[str],
    ) -> BatchDeleteDocumentsResponse:
        return await self._client._request(
            "POST",
            f"{_col_path(collection)}/documents/batch/delete",
            json={"document_ids": document_ids},
        )
