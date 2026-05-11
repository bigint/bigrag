from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import sqlalchemy as sa

from rag_computer.db.models import (
    ConnectorAccount,
    ConnectorProviderConfig,
    ConnectorSource,
    ConnectorSyncJob,
)
from rag_computer.routers._documents import SUPPORTED_EXTENSIONS
from rag_computer.services.connector_core import (
    ConnectorAuthError,
    ConnectorConfigError,
    ConnectorError,
    ConnectorNotFoundError,
    ConnectorScheduler,
    DownloadedConnectorFile,
    RemoteConnectorFile,
    account_public,
    config_public,
    configured,
    create_source,
    create_sync_job,
    delete_source,
    disconnect_account,
    get_connector_account,
    get_provider_config,
    list_sources,
    oauth_error_redirect_url,
    oauth_redirect_url,
    parse_dt,
    prepare_oauth_account,
    run_due_syncs,
    source_public,
    sync_connector_job,
    sync_job_public,
    trigger_sync,
    update_source,
    upsert_provider_config,
    utcnow,
)
from rag_computer.utils import safe_create_task

GOOGLE_PROVIDER = "google_drive"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDE_MIME = "application/vnd.google-apps.presentation"
GOOGLE_OAUTH_SCOPES = (
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive.readonly",
)
GOOGLE_DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
GOOGLE_DRIVE_FULL_SCOPE = "https://www.googleapis.com/auth/drive"
GOOGLE_FILE_FIELDS = "id,name,mimeType,modifiedTime,md5Checksum,size,version,trashed,webViewLink"


class GoogleDriveError(ConnectorError):
    pass


class GoogleDriveConfigError(ConnectorConfigError, GoogleDriveError):
    pass


class GoogleDriveAuthError(ConnectorAuthError, GoogleDriveError):
    pass


class GoogleDriveNotFoundError(ConnectorNotFoundError, GoogleDriveError):
    pass


def _google_error_payload(response: httpx.Response) -> tuple[str, set[str], str | None]:
    try:
        payload = response.json()
    except ValueError:
        return response.text, set(), None

    error = payload.get("error")
    if not isinstance(error, dict):
        return response.text, set(), None

    message = str(error.get("message") or response.text)
    reasons = {
        str(item.get("reason"))
        for item in error.get("errors", [])
        if isinstance(item, dict) and item.get("reason")
    }
    activation_url: str | None = None
    for detail in error.get("details", []):
        if not isinstance(detail, dict):
            continue
        reason = detail.get("reason")
        if reason:
            reasons.add(str(reason))
        metadata = detail.get("metadata")
        if isinstance(metadata, dict) and metadata.get("activationUrl"):
            activation_url = str(metadata["activationUrl"])
    return message, reasons, activation_url


RemoteDriveFile = RemoteConnectorFile
DownloadedDriveFile = DownloadedConnectorFile


def _remote_from_payload(payload: dict[str, Any]) -> RemoteDriveFile:
    return RemoteDriveFile(
        id=str(payload.get("id") or ""),
        name=str(payload.get("name") or "Untitled"),
        mime_type=str(payload.get("mimeType") or ""),
        modified_time=parse_dt(payload.get("modifiedTime")),
        md5_checksum=payload.get("md5Checksum"),
        size=int(payload["size"]) if str(payload.get("size") or "").isdigit() else None,
        version=str(payload.get("version")) if payload.get("version") is not None else None,
        web_url=payload.get("webViewLink"),
    )


def _account_has_required_scope(account: ConnectorAccount | None) -> bool:
    scopes = set(account.scopes or []) if account else set()
    return GOOGLE_DRIVE_READONLY_SCOPE in scopes or GOOGLE_DRIVE_FULL_SCOPE in scopes


def _escape_drive_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _sync_support_error(remote: RemoteDriveFile) -> str | None:
    if remote.mime_type == GOOGLE_FOLDER_MIME:
        return None
    file_ext = _extension_for_remote(remote)
    if not file_ext:
        return "Unsupported Drive file type"
    if file_ext not in SUPPORTED_EXTENSIONS:
        return f"Unsupported file type {file_ext}"
    return None


def google_drive_file_public(remote: RemoteDriveFile) -> dict[str, Any]:
    unsupported_reason = _sync_support_error(remote)
    return {
        "id": remote.id,
        "name": remote.name,
        "mime_type": remote.mime_type,
        "source_type": "folder" if remote.mime_type == GOOGLE_FOLDER_MIME else "file",
        "modified_time": remote.modified_time,
        "size": remote.size,
        "web_url": remote.web_url,
        "sync_supported": unsupported_reason is None,
        "unsupported_reason": unsupported_reason,
    }


def _drive_metadata(source: ConnectorSource, remote: RemoteDriveFile) -> dict[str, Any]:
    return {
        **dict(source.meta or {}),
        "source": "google_drive",
        "connector": GOOGLE_PROVIDER,
        "google_drive": {
            "source_id": str(source.id),
            "root_id": source.root_id,
            "root_name": source.root_name,
            "remote_id": remote.id,
            "remote_name": remote.name,
            "remote_mime_type": remote.mime_type,
            "remote_checksum": remote.md5_checksum,
            "remote_version": remote.version,
            "remote_modified_time": (
                remote.modified_time.isoformat() if remote.modified_time else None
            ),
            "web_url": remote.web_url,
        },
    }


def _sanitize_filename(name: str, file_ext: str) -> str:
    cleaned = "".join("_" if c in "\x00/\\:" else c for c in name).strip() or "document"
    if file_ext and not cleaned.lower().endswith(file_ext.lower()):
        cleaned = f"{cleaned}{file_ext}"
    return cleaned


_MIME_EXTENSIONS = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
    "text/tab-separated-values": ".tsv",
    "application/json": ".json",
    "application/xml": ".xml",
    "text/xml": ".xml",
    "text/html": ".html",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/tiff": ".tiff",
    "image/bmp": ".bmp",
}

_GOOGLE_EXPORTS = {
    GOOGLE_DOC_MIME: (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
    GOOGLE_SHEET_MIME: (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    GOOGLE_SLIDE_MIME: (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
}


def _extension_for_remote(remote: RemoteDriveFile) -> str | None:
    if remote.mime_type in _GOOGLE_EXPORTS:
        return _GOOGLE_EXPORTS[remote.mime_type][1]
    ext = Path(remote.name).suffix.lower()
    if ext:
        return ext
    return _MIME_EXTENSIONS.get(remote.mime_type)


class GoogleDriveClient:
    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._transport = transport
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=self._timeout)

    async def exchange_code(
        self,
        *,
        config: ConnectorProviderConfig,
        code: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        async with self._client() as client:
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
        async with self._client() as client:
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
            error = payload.get("error_description") or payload.get("error") or response.text
            raise GoogleDriveAuthError(str(error))
        return response.json()

    async def userinfo(self, access_token: str) -> dict[str, Any]:
        async with self._client() as client:
            response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if response.status_code >= 400:
            raise GoogleDriveAuthError(response.text)
        return response.json()

    async def get_file(self, access_token: str, file_id: str) -> RemoteDriveFile:
        async with self._client() as client:
            response = await client.get(
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
        async with self._client() as client:
            while True:
                response = await client.get(
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

        async with self._client() as client:
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

        async with self._client() as client:
            response = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        self._raise_for_status(response)
        content = response.content
        if not content:
            raise ValueError(f"Google Drive file '{remote.name}' is empty")
        filename = _sanitize_filename(remote.name, file_ext)
        return DownloadedDriveFile(
            remote=remote,
            filename=filename,
            file_ext=file_ext,
            content=content,
            content_hash=hashlib.sha256(content).hexdigest(),
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


async def get_google_config(session) -> ConnectorProviderConfig | None:
    return await get_provider_config(session, GOOGLE_PROVIDER)


def google_config_public(
    config: ConnectorProviderConfig | None,
    *,
    callback_url: str,
) -> dict[str, Any]:
    return config_public(config, provider=GOOGLE_PROVIDER, callback_url=callback_url)


async def upsert_google_config(
    session,
    *,
    enabled: bool,
    client_id: str,
    client_secret: str | None,
) -> ConnectorProviderConfig:
    return await upsert_provider_config(
        session,
        provider=GOOGLE_PROVIDER,
        enabled=enabled,
        client_id=client_id,
        client_secret=client_secret,
    )


async def get_google_account(session, user_id: str) -> ConnectorAccount | None:
    return await get_connector_account(session, provider=GOOGLE_PROVIDER, user_id=user_id)


def google_account_public(
    *,
    config: ConnectorProviderConfig | None,
    account: ConnectorAccount | None,
) -> dict[str, Any]:
    return account_public(
        provider=GOOGLE_PROVIDER,
        config=config,
        account=account,
        has_required_scope=_account_has_required_scope,
    )


async def build_google_oauth_url(
    session,
    *,
    user_id: str,
    redirect_uri: str,
    redirect_path: str,
    redirect_origin: str | None = None,
) -> str:
    config = await get_google_config(session)
    if not configured(config) or config is None:
        raise GoogleDriveConfigError("Google Drive connector is not configured")

    _, state = await prepare_oauth_account(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        redirect_path=redirect_path,
        redirect_origin=redirect_origin,
    )

    params = {
        "client_id": config.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    query = httpx.QueryParams(params)
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


async def complete_google_oauth(
    session,
    *,
    user_id: str,
    code: str,
    state: str,
    redirect_uri: str,
) -> str:
    config = await get_google_config(session)
    if not configured(config) or config is None:
        raise GoogleDriveConfigError("Google Drive connector is not configured")

    account = await get_google_account(session, user_id)
    if account is None or not account.oauth_state or account.oauth_state != state:
        raise GoogleDriveAuthError("Invalid Google OAuth state")

    token_payload = await google_drive_client.exchange_code(
        config=config,
        code=code,
        redirect_uri=redirect_uri,
    )
    access_token = token_payload.get("access_token")
    refresh_token = token_payload.get("refresh_token") or account.refresh_token
    if not access_token or not refresh_token:
        raise GoogleDriveAuthError(
            "Google did not return a refresh token. Reconnect and approve offline access."
        )

    info = await google_drive_client.userinfo(access_token)
    expires_in = int(token_payload.get("expires_in") or 3600)
    account.account_email = info.get("email") or account.account_email
    account.access_token = access_token
    account.refresh_token = refresh_token
    account.token_expires_at = utcnow() + timedelta(seconds=max(60, expires_in - 60))
    account.scopes = str(token_payload.get("scope") or " ".join(GOOGLE_OAUTH_SCOPES)).split()
    account.status = "connected"
    account.oauth_state = None
    account.last_connected_at = utcnow()
    redirect_path = oauth_redirect_url(
        account,
        str((account.meta or {}).get("redirect_path") or "/"),
    )
    await session.commit()
    return redirect_path


async def google_oauth_error_redirect_url(
    session,
    *,
    user_id: str,
    state: str | None,
    path: str,
) -> str:
    return await oauth_error_redirect_url(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        state=state,
        path=path,
    )


async def disconnect_google_account(session, *, user_id: str) -> None:
    await disconnect_account(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        source_error="Google account disconnected",
    )


async def _access_token_for_account(
    session,
    *,
    config: ConnectorProviderConfig,
    account: ConnectorAccount,
) -> str:
    if account.status != "connected" or not account.refresh_token:
        raise GoogleDriveAuthError("Google Drive account needs reconnection")
    if not _account_has_required_scope(account):
        account.status = "needs_reauth"
        account.access_token = None
        await session.execute(
            sa.update(ConnectorSource)
            .where(ConnectorSource.account_id == account.id)
            .values(
                status="needs_reauth",
                last_error="Reconnect Google Drive to grant read-only access",
            )
        )
        await session.commit()
        raise GoogleDriveAuthError("Reconnect Google Drive to grant read-only access")

    if account.access_token and account.token_expires_at and account.token_expires_at > utcnow():
        return account.access_token

    try:
        payload = await google_drive_client.refresh_access_token(
            config=config,
            refresh_token=account.refresh_token,
        )
    except GoogleDriveAuthError:
        account.status = "needs_reauth"
        account.access_token = None
        await session.execute(
            sa.update(ConnectorSource)
            .where(ConnectorSource.account_id == account.id)
            .values(status="needs_reauth", last_error="Google account needs reconnection")
        )
        await session.commit()
        raise

    account.access_token = payload["access_token"]
    expires_in = int(payload.get("expires_in") or 3600)
    account.token_expires_at = utcnow() + timedelta(seconds=max(60, expires_in - 60))
    if payload.get("scope"):
        account.scopes = str(payload["scope"]).split()
    await session.commit()
    return account.access_token


async def list_google_drive_files(
    session,
    *,
    user_id: str,
    parent_id: str = "root",
    query: str | None = None,
    page_token: str | None = None,
    page_size: int = 100,
) -> dict[str, Any]:
    config = await get_google_config(session)
    account = await get_google_account(session, user_id)
    if not configured(config) or config is None:
        raise GoogleDriveConfigError("Google Drive connector is not configured")
    if account is None or account.status != "connected":
        raise GoogleDriveAuthError("Connect Google Drive before browsing files")
    try:
        access_token = await _access_token_for_account(session, config=config, account=account)
        files, next_page_token = await google_drive_client.list_files(
            access_token=access_token,
            parent_id=parent_id,
            query=query,
            page_token=page_token,
            page_size=page_size,
        )
    except GoogleDriveAuthError:
        account.status = "needs_reauth"
        account.access_token = None
        await session.commit()
        raise
    return {
        "provider": GOOGLE_PROVIDER,
        "parent_id": parent_id or "root",
        "query": query or "",
        "files": [google_drive_file_public(file) for file in files],
        "next_page_token": next_page_token,
    }


def google_source_public(row: tuple[ConnectorSource, ConnectorAccount]) -> dict[str, Any]:
    return source_public(GOOGLE_PROVIDER, row)


def google_sync_job_public(job: ConnectorSyncJob) -> dict[str, Any]:
    return sync_job_public(GOOGLE_PROVIDER, job)


async def list_google_sources(
    session,
    *,
    user_id: str,
    collection_name: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    return await list_sources(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        collection_name=collection_name,
    )


def _infer_source_type(root_mime_type: str) -> str:
    return "folder" if root_mime_type == GOOGLE_FOLDER_MIME else "file"


async def create_google_source(
    session,
    *,
    user_id: str,
    collection_name: str,
    root_id: str,
    root_name: str,
    root_mime_type: str,
    source_type: str | None,
    metadata: dict,
) -> tuple[ConnectorSource, ConnectorSyncJob]:
    config = await get_google_config(session)
    if not configured(config):
        raise GoogleDriveConfigError("Google Drive connector is not configured")
    account = await get_google_account(session, user_id)
    if account is None or account.status != "connected":
        raise GoogleDriveAuthError("Connect Google Drive before adding sources")

    return await create_source(
        session,
        provider=GOOGLE_PROVIDER,
        account=account,
        collection_name=collection_name,
        root_id=root_id,
        root_name=root_name,
        root_mime_type=root_mime_type,
        source_type=source_type,
        metadata=metadata,
        user_id=user_id,
        infer_source_type=_infer_source_type,
        start_sync_job=start_google_sync_job,
    )


async def create_google_sync_job(
    session,
    *,
    source: ConnectorSource,
    trigger: str,
    user_id: str | None,
    commit: bool = True,
) -> ConnectorSyncJob:
    return await create_sync_job(
        session,
        provider=GOOGLE_PROVIDER,
        source=source,
        trigger=trigger,
        user_id=user_id,
        commit=commit,
    )


def start_google_sync_job(job_id: str) -> None:
    safe_create_task(sync_google_drive_job(job_id), name=f"google_drive_sync:{job_id}")


async def trigger_google_sync(
    session,
    *,
    user_id: str,
    source_id: str,
    trigger: str = "manual",
) -> ConnectorSyncJob:
    return await trigger_sync(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        source_id=source_id,
        not_found_message="Google Drive source not found",
        start_sync_job=start_google_sync_job,
        trigger=trigger,
    )


async def update_google_source(
    session,
    *,
    user_id: str,
    source_id: str,
    schedule_enabled: bool | None,
    sync_interval_hours: int | None,
) -> ConnectorSource:
    return await update_source(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        source_id=source_id,
        not_found_message="Google Drive source not found",
        schedule_enabled=schedule_enabled,
        sync_interval_hours=sync_interval_hours,
    )


async def delete_google_source(
    session,
    *,
    user_id: str,
    source_id: str,
) -> None:
    await delete_source(
        session,
        provider=GOOGLE_PROVIDER,
        user_id=user_id,
        source_id=source_id,
        not_found_message="Google Drive source not found",
    )


class GoogleDriveSyncAdapter:
    provider = GOOGLE_PROVIDER
    not_configured_message = "Google Drive connector is not configured"
    reauth_message = "Google account needs reconnection"
    partial_failure_message = "Some Drive files failed to sync"

    async def access_token_for_account(
        self,
        session,
        *,
        config: ConnectorProviderConfig,
        account: ConnectorAccount,
    ) -> str:
        return await _access_token_for_account(session, config=config, account=account)

    async def iter_files(
        self,
        *,
        access_token: str,
        source: ConnectorSource,
    ) -> list[RemoteDriveFile]:
        return await google_drive_client.iter_files(
            access_token=access_token,
            root_id=source.root_id,
            source_type=source.source_type,
        )

    async def download(
        self,
        *,
        access_token: str,
        remote: RemoteDriveFile,
    ) -> DownloadedDriveFile:
        return await google_drive_client.download(access_token, remote)

    def metadata(self, *, source: ConnectorSource, remote: RemoteDriveFile) -> dict[str, Any]:
        return _drive_metadata(source, remote)


google_drive_sync_adapter = GoogleDriveSyncAdapter()


async def sync_google_drive_job(job_id: str) -> None:
    await sync_connector_job(job_id, google_drive_sync_adapter)


async def run_due_google_syncs(limit: int = 10) -> int:
    return await run_due_syncs(
        provider=GOOGLE_PROVIDER,
        start_sync_job=start_google_sync_job,
        limit=limit,
    )


google_drive_scheduler = ConnectorScheduler(
    provider=GOOGLE_PROVIDER,
    start_sync_job=start_google_sync_job,
)
