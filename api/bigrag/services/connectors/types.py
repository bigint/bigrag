from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from bigrag.db.models import ConnectorAccount, ConnectorProviderConfig, ConnectorSource


class ConnectorError(RuntimeError):
    pass


class ConnectorConfigError(ConnectorError):
    pass


class ConnectorAuthError(ConnectorError):
    pass


class ConnectorNotFoundError(ConnectorError):
    pass


@dataclass(frozen=True)
class RemoteConnectorFile:
    id: str
    name: str
    mime_type: str
    modified_time: datetime | None = None
    md5_checksum: str | None = None
    size: int | None = None
    version: str | None = None
    web_url: str | None = None


@dataclass(frozen=True)
class DownloadedConnectorFile:
    remote: RemoteConnectorFile
    filename: str
    file_ext: str
    content: bytes
    content_hash: str


@dataclass
class ConnectorSyncCounters:
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


class ConnectorSyncAdapter(Protocol):
    provider: str
    not_configured_message: str
    reauth_message: str
    partial_failure_message: str

    async def access_token_for_account(
        self,
        session: Any,
        *,
        config: ConnectorProviderConfig,
        account: ConnectorAccount,
    ) -> str: ...

    async def iter_files(
        self,
        *,
        access_token: str,
        source: ConnectorSource,
    ) -> list[RemoteConnectorFile]: ...

    async def download(
        self,
        *,
        access_token: str,
        remote: RemoteConnectorFile,
    ) -> DownloadedConnectorFile: ...

    def metadata(
        self,
        *,
        source: ConnectorSource,
        remote: RemoteConnectorFile,
    ) -> dict[str, Any]: ...
