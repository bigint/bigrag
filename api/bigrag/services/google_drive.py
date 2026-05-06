from __future__ import annotations

import asyncio
import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

from bigrag.db.engine import session_factory
from bigrag.db.models import (
    Collection,
    ConnectorAccount,
    ConnectorDocument,
    ConnectorProviderConfig,
    ConnectorSource,
    ConnectorSyncJob,
    Document,
)
from bigrag.logging import get_logger
from bigrag.routers._documents import (
    SUPPORTED_EXTENSIONS,
    prepare_document_metadata,
    recount_collection_documents,
)
from bigrag.services import collection_cache
from bigrag.services.file_validation import InvalidFileContentError, validate_upload
from bigrag.services.ingestion_job import create_ingestion_job
from bigrag.services.queue import ingestion_queue
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.storage import get_storage
from bigrag.services.vector_store import vector_store
from bigrag.utils import safe_create_task

logger = get_logger("bigrag.google_drive")

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


class GoogleDriveError(RuntimeError):
    pass


class GoogleDriveConfigError(GoogleDriveError):
    pass


class GoogleDriveAuthError(GoogleDriveError):
    pass


class GoogleDriveNotFoundError(GoogleDriveError):
    pass


@dataclass(frozen=True)
class RemoteDriveFile:
    id: str
    name: str
    mime_type: str
    modified_time: datetime | None = None
    md5_checksum: str | None = None
    size: int | None = None
    version: str | None = None
    web_url: str | None = None


@dataclass(frozen=True)
class DownloadedDriveFile:
    remote: RemoteDriveFile
    filename: str
    file_ext: str
    content: bytes
    content_hash: str


@dataclass
class SyncCounters:
    found: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    deleted: int = 0
    failed: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def add_error(self, remote_id: str, name: str, error: str) -> None:
        self.failed += 1
        if len(self.errors) < 50:
            self.errors.append({"remote_id": remote_id, "name": name, "error": error})


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _next_sync_at(source: ConnectorSource, *, from_time: datetime | None = None) -> datetime | None:
    if not source.schedule_enabled:
        return None
    interval = max(1, int(source.sync_interval_hours or 24))
    return (from_time or _now()) + timedelta(hours=interval)


def _configured(config: ConnectorProviderConfig | None) -> bool:
    return bool(config and config.enabled and config.client_id and config.client_secret)


def _remote_from_payload(payload: dict[str, Any]) -> RemoteDriveFile:
    return RemoteDriveFile(
        id=str(payload.get("id") or ""),
        name=str(payload.get("name") or "Untitled"),
        mime_type=str(payload.get("mimeType") or ""),
        modified_time=_parse_dt(payload.get("modifiedTime")),
        md5_checksum=payload.get("md5Checksum"),
        size=int(payload["size"]) if str(payload.get("size") or "").isdigit() else None,
        version=str(payload.get("version")) if payload.get("version") is not None else None,
        web_url=payload.get("webViewLink"),
    )


def _remote_signature(remote: RemoteDriveFile) -> str | None:
    return remote.md5_checksum or remote.version


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


def _collection_dict(collection: Collection) -> dict:
    return {
        "id": collection.id,
        "name": collection.name,
        "embedding_provider": collection.embedding_provider,
        "embedding_model": collection.embedding_model,
        "dimension": collection.dimension,
        "chunk_size": collection.chunk_size,
        "chunk_overlap": collection.chunk_overlap,
        "chunk_strategy": collection.chunk_strategy or "paragraph",
        "tenant_field": collection.tenant_field,
        "metadata_schema": collection.metadata_schema,
    }


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

        async with self._client() as client:
            response = await client.get(
                "https://www.googleapis.com/drive/v3/files",
                params={
                    "q": q,
                    "fields": f"nextPageToken,files({GOOGLE_FILE_FIELDS})",
                    "pageSize": max(1, min(page_size, 100)),
                    "pageToken": page_token,
                    "includeItemsFromAllDrives": "true",
                    "supportsAllDrives": "true",
                    "orderBy": "folder,name",
                },
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
        if response.status_code == 401:
            raise GoogleDriveAuthError(response.text)
        if response.status_code == 404:
            raise GoogleDriveNotFoundError(response.text)
        response.raise_for_status()


google_drive_client = GoogleDriveClient()


async def get_google_config(session) -> ConnectorProviderConfig | None:
    return await session.scalar(
        sa.select(ConnectorProviderConfig).where(
            ConnectorProviderConfig.provider == GOOGLE_PROVIDER
        )
    )


def google_config_public(
    config: ConnectorProviderConfig | None,
    *,
    callback_url: str,
) -> dict[str, Any]:
    return {
        "provider": GOOGLE_PROVIDER,
        "configured": _configured(config),
        "enabled": bool(config.enabled) if config else False,
        "client_id": config.client_id if config else "",
        "has_client_secret": bool(config and config.client_secret),
        "callback_url": callback_url,
        "created_at": config.created_at if config else None,
        "updated_at": config.updated_at if config else None,
    }


async def upsert_google_config(
    session,
    *,
    enabled: bool,
    client_id: str,
    client_secret: str | None,
) -> ConnectorProviderConfig:
    existing = await get_google_config(session)
    values = {
        "provider": GOOGLE_PROVIDER,
        "enabled": enabled,
        "client_id": client_id.strip(),
    }
    if client_secret is not None:
        values["client_secret"] = client_secret.strip() or None
    elif existing is not None:
        values["client_secret"] = existing.client_secret

    stmt = pg_insert(ConnectorProviderConfig).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ConnectorProviderConfig.provider],
        set_={
            "enabled": stmt.excluded.enabled,
            "client_id": stmt.excluded.client_id,
            "client_secret": stmt.excluded.client_secret,
            "updated_at": sa.func.now(),
        },
    ).returning(ConnectorProviderConfig)
    config = (await session.execute(stmt)).scalar_one()
    await session.commit()
    await session.refresh(config)
    return config


async def get_google_account(session, user_id: str | uuid.UUID) -> ConnectorAccount | None:
    return await session.scalar(
        sa.select(ConnectorAccount)
        .where(ConnectorAccount.provider == GOOGLE_PROVIDER)
        .where(ConnectorAccount.user_id == uuid.UUID(str(user_id)))
    )


def google_account_public(
    *,
    config: ConnectorProviderConfig | None,
    account: ConnectorAccount | None,
) -> dict[str, Any]:
    scope_ok = _account_has_required_scope(account)
    status = account.status if account else None
    if account and account.status == "connected" and not scope_ok:
        status = "needs_reauth"
    return {
        "provider": GOOGLE_PROVIDER,
        "configured": _configured(config),
        "connected": bool(
            account and account.status == "connected" and account.refresh_token and scope_ok
        ),
        "status": status,
        "email": account.account_email if account else None,
        "scopes": list(account.scopes or []) if account else [],
        "token_expires_at": account.token_expires_at if account else None,
        "last_connected_at": account.last_connected_at if account else None,
    }


async def build_google_oauth_url(
    session,
    *,
    user_id: str,
    redirect_uri: str,
    redirect_path: str,
) -> str:
    config = await get_google_config(session)
    if not _configured(config) or config is None:
        raise GoogleDriveConfigError("Google Drive connector is not configured")

    state = secrets.token_urlsafe(32)
    user_uuid = uuid.UUID(user_id)
    account = await get_google_account(session, user_uuid)
    if account is None:
        account = ConnectorAccount(
            provider=GOOGLE_PROVIDER,
            user_id=user_uuid,
            status="pending",
        )
        session.add(account)
    account.oauth_state = state
    account.status = "pending" if account.status != "connected" else account.status
    account.meta = {**dict(account.meta or {}), "redirect_path": redirect_path or "/"}
    await session.commit()

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
    if not _configured(config) or config is None:
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
    account.token_expires_at = _now() + timedelta(seconds=max(60, expires_in - 60))
    account.scopes = str(token_payload.get("scope") or " ".join(GOOGLE_OAUTH_SCOPES)).split()
    account.status = "connected"
    account.oauth_state = None
    account.last_connected_at = _now()
    redirect_path = str((account.meta or {}).get("redirect_path") or "/")
    await session.commit()
    return redirect_path


async def disconnect_google_account(session, *, user_id: str) -> None:
    account = await get_google_account(session, user_id)
    if account is None:
        return
    account.status = "revoked"
    account.access_token = None
    account.refresh_token = None
    account.token_expires_at = None
    account.oauth_state = None
    await session.execute(
        sa.update(ConnectorSource)
        .where(ConnectorSource.account_id == account.id)
        .values(status="needs_reauth", last_error="Google account disconnected")
    )
    await session.commit()


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

    if account.access_token and account.token_expires_at and account.token_expires_at > _now():
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
    account.token_expires_at = _now() + timedelta(seconds=max(60, expires_in - 60))
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
    if not _configured(config) or config is None:
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
    source, account = row
    return {
        "id": str(source.id),
        "provider": GOOGLE_PROVIDER,
        "collection_name": source.collection_name,
        "root_id": source.root_id,
        "root_name": source.root_name,
        "root_mime_type": source.root_mime_type,
        "source_type": source.source_type,
        "status": source.status,
        "schedule_enabled": source.schedule_enabled,
        "sync_interval_hours": source.sync_interval_hours,
        "last_sync_at": source.last_sync_at,
        "next_sync_at": source.next_sync_at,
        "last_error": source.last_error,
        "account_email": account.account_email,
        "metadata": source.meta or {},
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def google_sync_job_public(job: ConnectorSyncJob) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "provider": GOOGLE_PROVIDER,
        "source_id": str(job.source_id) if job.source_id else None,
        "trigger": job.trigger,
        "status": job.status,
        "total_found": job.total_found,
        "total_created": job.total_created,
        "total_updated": job.total_updated,
        "total_skipped": job.total_skipped,
        "total_deleted": job.total_deleted,
        "total_failed": job.total_failed,
        "error_message": job.error_message,
        "details": job.details or {},
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


async def list_google_sources(
    session,
    *,
    user_id: str,
    collection_name: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    stmt = (
        sa.select(ConnectorSource, ConnectorAccount)
        .join(ConnectorAccount, ConnectorAccount.id == ConnectorSource.account_id)
        .where(ConnectorAccount.user_id == uuid.UUID(user_id))
        .where(ConnectorSource.provider == GOOGLE_PROVIDER)
        .order_by(ConnectorSource.created_at.desc())
    )
    if collection_name:
        stmt = stmt.where(ConnectorSource.collection_name == collection_name)
    rows = (await session.execute(stmt)).all()
    return [google_source_public(row) for row in rows], len(rows)


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
    if not _configured(config):
        raise GoogleDriveConfigError("Google Drive connector is not configured")
    account = await get_google_account(session, user_id)
    if account is None or account.status != "connected":
        raise GoogleDriveAuthError("Connect Google Drive before adding sources")

    collection = await session.scalar(
        sa.select(Collection).where(Collection.name == collection_name)
    )
    if collection is None:
        raise ValueError("Collection not found")

    inferred_type = "folder" if root_mime_type == GOOGLE_FOLDER_MIME else "file"
    source = ConnectorSource(
        provider=GOOGLE_PROVIDER,
        account_id=account.id,
        collection_id=collection.id,
        collection_name=collection.name,
        root_id=root_id,
        root_name=root_name,
        root_mime_type=root_mime_type or "",
        source_type=source_type or inferred_type,
        schedule_enabled=True,
        sync_interval_hours=24,
        status="syncing",
        next_sync_at=_now() + timedelta(hours=24),
        meta=dict(metadata or {}),
    )
    session.add(source)
    try:
        await session.flush()
    except sa.exc.IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            sa.select(ConnectorSource)
            .where(ConnectorSource.account_id == account.id)
            .where(ConnectorSource.collection_id == collection.id)
            .where(ConnectorSource.root_id == root_id)
        )
        if existing is None:
            raise
        job = await create_google_sync_job(
            session,
            source=existing,
            trigger="initial",
            user_id=user_id,
            commit=False,
        )
        await session.commit()
        if job.status == "pending" and job.started_at is None:
            start_google_sync_job(str(job.id))
        return existing, job

    job = await create_google_sync_job(
        session,
        source=source,
        trigger="initial",
        user_id=user_id,
        commit=False,
    )
    await session.commit()
    await session.refresh(source)
    await session.refresh(job)
    if job.status == "pending" and job.started_at is None:
        start_google_sync_job(str(job.id))
    return source, job


async def create_google_sync_job(
    session,
    *,
    source: ConnectorSource,
    trigger: str,
    user_id: str | None,
    commit: bool = True,
) -> ConnectorSyncJob:
    existing = await session.scalar(
        sa.select(ConnectorSyncJob)
        .where(ConnectorSyncJob.source_id == source.id)
        .where(ConnectorSyncJob.status.in_(("pending", "running")))
        .order_by(ConnectorSyncJob.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        return existing

    source.status = "syncing"
    source.last_error = None
    job = ConnectorSyncJob(
        provider=GOOGLE_PROVIDER,
        source_id=source.id,
        trigger=trigger,
        status="pending",
        started_by=uuid.UUID(user_id) if user_id else None,
    )
    session.add(job)
    if commit:
        await session.commit()
        await session.refresh(job)
    return job


def start_google_sync_job(job_id: str) -> None:
    safe_create_task(sync_google_drive_job(job_id), name=f"google_drive_sync:{job_id}")


async def trigger_google_sync(
    session,
    *,
    user_id: str,
    source_id: str,
    trigger: str = "manual",
) -> ConnectorSyncJob:
    source = await _source_for_user(session, source_id=source_id, user_id=user_id)
    job = await create_google_sync_job(
        session,
        source=source,
        trigger=trigger,
        user_id=user_id,
    )
    if job.status == "pending" and job.started_at is None:
        start_google_sync_job(str(job.id))
    return job


async def update_google_source(
    session,
    *,
    user_id: str,
    source_id: str,
    schedule_enabled: bool | None,
    sync_interval_hours: int | None,
) -> ConnectorSource:
    source = await _source_for_user(session, source_id=source_id, user_id=user_id)
    if schedule_enabled is not None:
        source.schedule_enabled = schedule_enabled
    if sync_interval_hours is not None:
        source.sync_interval_hours = sync_interval_hours
    source.next_sync_at = _next_sync_at(source)
    await session.commit()
    await session.refresh(source)
    return source


async def delete_google_source(
    session,
    *,
    user_id: str,
    source_id: str,
) -> None:
    source = await _source_for_user(session, source_id=source_id, user_id=user_id)
    await session.delete(source)
    await session.commit()


async def _source_for_user(session, *, source_id: str, user_id: str) -> ConnectorSource:
    row = (
        await session.execute(
            sa.select(ConnectorSource)
            .join(ConnectorAccount, ConnectorAccount.id == ConnectorSource.account_id)
            .where(ConnectorSource.id == uuid.UUID(source_id))
            .where(ConnectorAccount.user_id == uuid.UUID(user_id))
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("Google Drive source not found")
    return row


async def sync_google_drive_job(job_id: str) -> None:
    counters = SyncCounters()
    now = _now()
    async with session_factory()() as session:
        job = await session.get(ConnectorSyncJob, uuid.UUID(job_id))
        if job is None or job.source_id is None:
            return
        source = await session.get(ConnectorSource, job.source_id)
        if source is None:
            return
        account = await session.get(ConnectorAccount, source.account_id)
        config = await get_google_config(session)
        collection = await session.get(Collection, source.collection_id)

        job.status = "running"
        job.started_at = now
        source.status = "syncing"
        source.last_error = None
        await session.commit()

        if account is None or config is None or not _configured(config) or collection is None:
            await _fail_sync(
                session,
                job=job,
                source=source,
                message="Google Drive connector is not configured",
            )
            return

        try:
            access_token = await _access_token_for_account(session, config=config, account=account)
            try:
                remotes = await google_drive_client.iter_files(
                    access_token=access_token,
                    root_id=source.root_id,
                    source_type=source.source_type,
                )
            except GoogleDriveNotFoundError:
                remotes = []

            counters.found = len(remotes)
            seen_remote_ids = {remote.id for remote in remotes}
            manifests = {
                manifest.remote_id: manifest
                for manifest in (
                    await session.scalars(
                        sa.select(ConnectorDocument).where(ConnectorDocument.source_id == source.id)
                    )
                ).all()
            }

            for remote in remotes:
                manifest = manifests.get(remote.id)
                try:
                    downloaded = await google_drive_client.download(access_token, remote)
                    await _sync_downloaded_file(
                        session,
                        source=source,
                        collection=collection,
                        manifest=manifest,
                        downloaded=downloaded,
                        counters=counters,
                    )
                except (InvalidFileContentError, ValueError) as exc:
                    counters.add_error(remote.id, remote.name, str(exc))
                except Exception as exc:
                    logger.warning(
                        "google_drive: file sync failed",
                        source_id=str(source.id),
                        remote_id=remote.id,
                        error=f"{exc.__class__.__name__}: {exc}",
                    )
                    counters.add_error(remote.id, remote.name, str(exc))

            missing = [
                manifest
                for remote_id, manifest in manifests.items()
                if remote_id not in seen_remote_ids
            ]
            for manifest in missing:
                await _delete_synced_document(
                    session,
                    source=source,
                    manifest=manifest,
                    counters=counters,
                )

            completed = _now()
            job.status = "complete" if counters.failed == 0 else "failed"
            job.error_message = None if counters.failed == 0 else "Some Drive files failed to sync"
            job.completed_at = completed
            _apply_counters(job, counters)
            source.status = "idle" if counters.failed == 0 else "error"
            source.last_sync_at = completed
            source.next_sync_at = _next_sync_at(source, from_time=completed)
            source.last_error = job.error_message
            await recount_collection_documents(session, source.collection_id)
            await session.commit()
            await collection_cache.invalidate(source.collection_name)
            await invalidate_collection_query_cache(source.collection_name)
            logger.info(
                "google_drive: sync complete",
                job_id=job_id,
                source_id=str(source.id),
                found=counters.found,
                created=counters.created,
                updated=counters.updated,
                skipped=counters.skipped,
                deleted=counters.deleted,
                failed=counters.failed,
            )
        except GoogleDriveAuthError as exc:
            account.status = "needs_reauth"
            source.status = "needs_reauth"
            source.last_error = "Google account needs reconnection"
            await _fail_sync(session, job=job, source=source, message=str(exc))
        except Exception as exc:
            logger.exception("google_drive: sync job failed", job_id=job_id)
            await _fail_sync(session, job=job, source=source, message=str(exc))


async def _sync_downloaded_file(
    session,
    *,
    source: ConnectorSource,
    collection: Collection,
    manifest: ConnectorDocument | None,
    downloaded: DownloadedDriveFile,
    counters: SyncCounters,
) -> None:
    remote = downloaded.remote
    existing_doc = await session.get(Document, manifest.document_id) if manifest else None
    if (
        manifest is not None
        and existing_doc is not None
        and existing_doc.status != "failed"
        and _manifest_unchanged(manifest, downloaded)
    ):
        counters.skipped += 1
        manifest.remote_name = remote.name
        manifest.remote_mime_type = remote.mime_type
        manifest.web_url = remote.web_url
        return

    validate_upload(downloaded.content, downloaded.file_ext)
    collection_dict = _collection_dict(collection)
    metadata = prepare_document_metadata(collection_dict, _drive_metadata(source, remote))
    storage = get_storage()

    if manifest is None:
        doc_id = uuid.uuid4()
        storage_key = f"{source.collection_name}/{doc_id}{downloaded.file_ext}"
        await storage.put(storage_key, downloaded.content)
        doc = Document(
            id=doc_id,
            collection_id=collection.id,
            filename=downloaded.filename,
            file_type=downloaded.file_ext.lstrip("."),
            file_size=len(downloaded.content),
            file_path=storage_key,
            content_hash=downloaded.content_hash,
            meta=metadata,
        )
        session.add(doc)
        await session.flush()
        session.add(_manifest_for_download(source=source, doc=doc, downloaded=downloaded))
        counters.created += 1
    else:
        doc = existing_doc
        if doc is None:
            manifest = None
            doc_id = uuid.uuid4()
            storage_key = f"{source.collection_name}/{doc_id}{downloaded.file_ext}"
            await storage.put(storage_key, downloaded.content)
            doc = Document(
                id=doc_id,
                collection_id=collection.id,
                filename=downloaded.filename,
                file_type=downloaded.file_ext.lstrip("."),
                file_size=len(downloaded.content),
                file_path=storage_key,
                content_hash=downloaded.content_hash,
                meta=metadata,
            )
            session.add(doc)
            await session.flush()
            session.add(_manifest_for_download(source=source, doc=doc, downloaded=downloaded))
            counters.created += 1
        else:
            await ingestion_queue.cancel_documents([str(doc.id)])
            await vector_store.delete_by_document(source.collection_name, str(doc.id))
            old_path = doc.file_path
            storage_key = f"{source.collection_name}/{doc.id}{downloaded.file_ext}"
            await storage.put(storage_key, downloaded.content)
            if old_path != storage_key:
                await storage.delete(old_path)
            doc.filename = downloaded.filename
            doc.file_type = downloaded.file_ext.lstrip(".")
            doc.file_size = len(downloaded.content)
            doc.file_path = storage_key
            doc.content_hash = downloaded.content_hash
            doc.status = "pending"
            doc.chunk_count = 0
            doc.token_count = 0
            doc.error_message = None
            doc.meta = metadata
            _update_manifest(manifest, downloaded)
            counters.updated += 1

    await session.flush()
    await session.commit()
    try:
        await ingestion_queue.enqueue(
            create_ingestion_job(
                document_id=str(doc.id),
                file_path=doc.file_path,
                collection_name=source.collection_name,
                collection=collection_dict,
            )
        )
    except Exception as exc:
        doc.status = "failed"
        doc.error_message = f"enqueue failed: {exc.__class__.__name__}: {exc}"
        await session.commit()
        raise


def _manifest_unchanged(manifest: ConnectorDocument, downloaded: DownloadedDriveFile) -> bool:
    remote = downloaded.remote
    signature = _remote_signature(remote)
    old_signature = manifest.remote_checksum or manifest.remote_version
    if signature and old_signature and signature == old_signature:
        return True
    return bool(manifest.content_hash and manifest.content_hash == downloaded.content_hash)


def _manifest_for_download(
    *,
    source: ConnectorSource,
    doc: Document,
    downloaded: DownloadedDriveFile,
) -> ConnectorDocument:
    remote = downloaded.remote
    return ConnectorDocument(
        source_id=source.id,
        document_id=doc.id,
        remote_id=remote.id,
        remote_name=remote.name,
        remote_mime_type=remote.mime_type,
        remote_checksum=remote.md5_checksum,
        remote_version=remote.version,
        remote_modified_time=remote.modified_time,
        content_hash=downloaded.content_hash,
        web_url=remote.web_url,
        status="active",
    )


def _update_manifest(manifest: ConnectorDocument, downloaded: DownloadedDriveFile) -> None:
    remote = downloaded.remote
    manifest.remote_name = remote.name
    manifest.remote_mime_type = remote.mime_type
    manifest.remote_checksum = remote.md5_checksum
    manifest.remote_version = remote.version
    manifest.remote_modified_time = remote.modified_time
    manifest.content_hash = downloaded.content_hash
    manifest.web_url = remote.web_url
    manifest.status = "active"


async def _delete_synced_document(
    session,
    *,
    source: ConnectorSource,
    manifest: ConnectorDocument,
    counters: SyncCounters,
) -> None:
    doc = await session.get(Document, manifest.document_id)
    if doc is not None:
        await ingestion_queue.cancel_documents([str(doc.id)])
        await vector_store.delete_by_document(source.collection_name, str(doc.id))
        await get_storage().delete(doc.file_path)
        await session.delete(doc)
    await session.delete(manifest)
    counters.deleted += 1


def _apply_counters(job: ConnectorSyncJob, counters: SyncCounters) -> None:
    job.total_found = counters.found
    job.total_created = counters.created
    job.total_updated = counters.updated
    job.total_skipped = counters.skipped
    job.total_deleted = counters.deleted
    job.total_failed = counters.failed
    job.details = {"errors": counters.errors}


async def _fail_sync(
    session,
    *,
    job: ConnectorSyncJob,
    source: ConnectorSource,
    message: str,
) -> None:
    job.status = "failed"
    job.error_message = message
    job.completed_at = _now()
    source.status = "needs_reauth" if source.status == "needs_reauth" else "error"
    source.last_error = message
    source.next_sync_at = _next_sync_at(source)
    await session.commit()


class GoogleDriveScheduler:
    def __init__(self, interval_seconds: int = 60) -> None:
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = safe_create_task(self._loop(), name="google_drive_scheduler")
        logger.info("google_drive: scheduler started", interval_seconds=self.interval_seconds)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("google_drive: scheduler stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await run_due_google_syncs()
            except Exception as exc:
                logger.warning("google_drive: scheduler tick failed", error=str(exc))
            await asyncio.sleep(self.interval_seconds)


async def run_due_google_syncs(limit: int = 10) -> int:
    job_ids: list[str] = []
    async with session_factory()() as session:
        rows = (
            await session.scalars(
                sa.select(ConnectorSource)
                .where(ConnectorSource.provider == GOOGLE_PROVIDER)
                .where(ConnectorSource.schedule_enabled.is_(True))
                .where(ConnectorSource.next_sync_at.is_not(None))
                .where(ConnectorSource.next_sync_at <= _now())
                .where(ConnectorSource.status != "syncing")
                .order_by(ConnectorSource.next_sync_at.asc())
                .limit(limit)
            )
        ).all()
        for source in rows:
            job = await create_google_sync_job(
                session,
                source=source,
                trigger="scheduled",
                user_id=None,
                commit=False,
            )
            await session.flush()
            if job.status == "pending" and job.started_at is None:
                job_ids.append(str(job.id))
        await session.commit()
    for job_id in job_ids:
        start_google_sync_job(job_id)
    return len(job_ids)


google_drive_scheduler = GoogleDriveScheduler()
