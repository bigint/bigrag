from __future__ import annotations

import asyncio
import hashlib
import random
import tempfile
from pathlib import Path
from typing import Any

import httpx

from bigrag.config import settings
from bigrag.db.models import ConnectorProviderConfig
from bigrag.routers._documents import SUPPORTED_EXTENSIONS
from bigrag.services.connectors.google_drive_types import (
    _GOOGLE_EXPORTS,
    GOOGLE_FILE_FIELDS,
    GOOGLE_FOLDER_MIME,
    DownloadedDriveFile,
    GoogleDriveAuthError,
    GoogleDriveConfigError,
    GoogleDriveError,
    GoogleDriveNotFoundError,
    RemoteDriveFile,
    _escape_drive_query,
    _extension_for_remote,
    _google_error_payload,
    _remote_from_payload,
    _sanitize_filename,
)


class GoogleDriveClient:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._transport = transport
        self._timeout = timeout
        self._http_client: httpx.AsyncClient | None = None

    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                transport=self._transport,
                timeout=self._timeout,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            )
        return self._http_client

    async def aclose(self) -> None:
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
        self._http_client = None

    async def _request_with_retry(self, method: str, url: str, **kw: Any) -> httpx.Response:
        client = self._client()
        delay = 1.0
        last: httpx.Response | None = None
        for attempt in range(5):
            response = await client.request(method, url, **kw)
            if response.status_code not in (429, 500, 502, 503, 504):
                return response
            last = response
            if attempt == 4:
                break
            sleep_for = min(delay, 64.0) + random.uniform(0, 1)
            await asyncio.sleep(sleep_for)
            delay = min(delay * 2, 64.0)
        assert last is not None
        return last

    async def exchange_code(
        self,
        *,
        config: ConnectorProviderConfig,
        code: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        client = self._client()
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        return self._token_response(response)

    async def refresh_access_token(
        self,
        *,
        config: ConnectorProviderConfig,
        refresh_token: str,
    ) -> dict[str, Any]:
        client = self._client()
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        return self._token_response(response)

    def _token_response(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            error = (
                payload.get("error_description") or payload.get("error") or "token request failed"
            )
            raise GoogleDriveAuthError(str(error)[:200])
        return response.json()

    async def userinfo(self, access_token: str) -> dict[str, Any]:
        client = self._client()
        response = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            error = (
                payload.get("error_description")
                or payload.get("error")
                or f"userinfo request failed with {response.status_code}"
            )
            raise GoogleDriveAuthError(str(error)[:200])
        return response.json()

    async def get_file(self, access_token: str, file_id: str) -> RemoteDriveFile:
        response = await self._request_with_retry(
            "GET",
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            params={
                "fields": GOOGLE_FILE_FIELDS,
                "supportsAllDrives": "true",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        payload = self._json_or_raise(response)
        remote = _remote_from_payload(payload)
        if not remote.id:
            raise GoogleDriveNotFoundError(f"Drive file {file_id!r} was not returned")
        return remote

    async def iter_files(
        self,
        *,
        access_token: str,
        root_id: str,
        source_type: str,
    ) -> list[RemoteDriveFile]:
        root = await self.get_file(access_token, root_id)
        if source_type == "file" or root.mime_type != GOOGLE_FOLDER_MIME:
            return [] if root.mime_type == GOOGLE_FOLDER_MIME else [root]

        files: list[RemoteDriveFile] = []
        stack = [root.id]
        while stack:
            folder_id = stack.pop()
            children = await self.list_children(access_token, folder_id)
            for child in children:
                if child.mime_type == GOOGLE_FOLDER_MIME:
                    stack.append(child.id)
                else:
                    files.append(child)
        return files

    async def list_children(self, access_token: str, folder_id: str) -> list[RemoteDriveFile]:
        files: list[RemoteDriveFile] = []
        page_token: str | None = None
        seen_tokens: set[str] = set()
        max_pages = 10000
        pages = 0
        while True:
            response = await self._request_with_retry(
                "GET",
                "https://www.googleapis.com/drive/v3/files",
                params={
                    "q": f"'{folder_id}' in parents and trashed=false",
                    "fields": f"nextPageToken,files({GOOGLE_FILE_FIELDS})",
                    "pageSize": 1000,
                    "pageToken": page_token,
                    "includeItemsFromAllDrives": "true",
                    "supportsAllDrives": "true",
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
            payload = self._json_or_raise(response)
            files.extend(_remote_from_payload(item) for item in payload.get("files", []))
            page_token = payload.get("nextPageToken")
            if not page_token:
                return files
            if page_token in seen_tokens:
                import warnings

                warnings.warn(
                    f"Google Drive list_children: repeated pageToken for folder {folder_id!r}",
                    stacklevel=2,
                )
                return files
            seen_tokens.add(page_token)
            pages += 1
            if pages >= max_pages:
                import warnings

                warnings.warn(
                    f"Google Drive list_children: hit max_pages={max_pages} for {folder_id!r}",
                    stacklevel=2,
                )
                return files

    async def list_files(
        self,
        *,
        access_token: str,
        parent_id: str = "root",
        query: str | None = None,
        page_token: str | None = None,
        page_size: int = 100,
    ) -> tuple[list[RemoteDriveFile], str | None]:
        search = (query or "").strip()
        if search:
            q = f"name contains '{_escape_drive_query(search)}' and trashed=false"
        else:
            folder_id = parent_id.strip() or "root"
            q = f"'{_escape_drive_query(folder_id)}' in parents and trashed=false"

        params: dict[str, str | int] = {
            "q": q,
            "fields": f"nextPageToken,files({GOOGLE_FILE_FIELDS})",
            "pageSize": max(1, min(page_size, 100)),
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
            "orderBy": "folder,name",
        }
        if page_token:
            params["pageToken"] = page_token

        client = self._client()
        response = await client.get(
            "https://www.googleapis.com/drive/v3/files",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        payload = self._json_or_raise(response)
        return (
            [_remote_from_payload(item) for item in payload.get("files", [])],
            payload.get("nextPageToken"),
        )

    async def download(self, access_token: str, remote: RemoteDriveFile) -> DownloadedDriveFile:
        file_ext = _extension_for_remote(remote)
        if not file_ext:
            raise ValueError(f"Unsupported Google Drive MIME type: {remote.mime_type}")
        if file_ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported Google Drive file type '{file_ext}' for '{remote.name}'")

        params: dict[str, str] = {"supportsAllDrives": "true"}
        if remote.mime_type in _GOOGLE_EXPORTS:
            export_mime, _ = _GOOGLE_EXPORTS[remote.mime_type]
            url = f"https://www.googleapis.com/drive/v3/files/{remote.id}/export"
            params = {"mimeType": export_mime}
        else:
            url = f"https://www.googleapis.com/drive/v3/files/{remote.id}"
            params["alt"] = "media"

        temp_dir = settings.upload_dir or None
        if temp_dir:
            Path(temp_dir).mkdir(parents=True, exist_ok=True)
        tmp = tempfile.NamedTemporaryFile(delete=False, dir=temp_dir, suffix=file_ext)
        tmp_path = Path(tmp.name)
        hasher = hashlib.sha256()
        total = 0
        client = self._client()
        try:
            delay = 1.0
            for attempt in range(5):
                hasher = hashlib.sha256()
                total = 0
                tmp.seek(0)
                tmp.truncate(0)
                async with client.stream(
                    "GET",
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                ) as response:
                    if response.status_code in (429, 500, 502, 503, 504) and attempt < 4:
                        await response.aread()
                        sleep_for = min(delay, 64.0) + random.uniform(0, 1)
                        await asyncio.sleep(sleep_for)
                        delay = min(delay * 2, 64.0)
                        continue
                    if response.status_code >= 400:
                        await response.aread()
                        self._raise_for_status(response)
                    async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        hasher.update(chunk)
                        tmp.write(chunk)
                        total += len(chunk)
                    break
            tmp.flush()
        except BaseException:
            try:
                tmp.close()
            finally:
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise
        tmp.close()
        if total == 0:
            try:
                tmp_path.unlink()
            except OSError:
                pass
            raise ValueError(f"Google Drive file '{remote.name}' is empty")
        filename = _sanitize_filename(remote.name, file_ext)
        return DownloadedDriveFile(
            remote=remote,
            filename=filename,
            file_ext=file_ext,
            path=tmp_path,
            file_size=total,
            content_hash=hasher.hexdigest(),
        )

    def _json_or_raise(self, response: httpx.Response) -> dict[str, Any]:
        self._raise_for_status(response)
        return response.json()

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        message, reasons, activation_url = _google_error_payload(response)
        if response.status_code == 401:
            raise GoogleDriveAuthError(message)
        if response.status_code == 404:
            raise GoogleDriveNotFoundError(message)
        if response.status_code == 403:
            if "accessNotConfigured" in reasons or "SERVICE_DISABLED" in reasons:
                suffix = (
                    f" Enable it here: {activation_url}"
                    if activation_url and activation_url not in message
                    else ""
                )
                raise GoogleDriveConfigError(f"{message}{suffix}")
            raise GoogleDriveAuthError(message)
        raise GoogleDriveError(message)


google_drive_client = GoogleDriveClient()
