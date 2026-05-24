from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from bigrag.db.models import ConnectorSource


class ConnectorError(RuntimeError):
    pass


class ConnectorDeleteSafetyError(ConnectorError):
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
    path: Path
    file_size: int
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
    partial_failure_message: str

    def iter_files(
        self,
        session: Any,
        *,
        source: ConnectorSource,
    ) -> AsyncIterator[list[RemoteConnectorFile]]: ...

    async def download(
        self,
        session: Any,
        *,
        source: ConnectorSource,
        remote: RemoteConnectorFile,
    ) -> DownloadedConnectorFile: ...

    def metadata(
        self,
        *,
        source: ConnectorSource,
        remote: RemoteConnectorFile,
    ) -> dict[str, Any]: ...
