from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from bigrag.db.models import ConnectorAccount, ConnectorSource
from bigrag.services.connector_core import (
    ConnectorAuthError,
    ConnectorConfigError,
    ConnectorError,
    ConnectorNotFoundError,
    DownloadedConnectorFile,
    RemoteConnectorFile,
    parse_dt,
)
from bigrag.services.documents import SUPPORTED_EXTENSIONS

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
