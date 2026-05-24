from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bigrag.db.models import Document, UploadSession, UploadSessionItem


@dataclass
class UploadSessionFileContext:
    upload_session: UploadSession
    existing: UploadSessionItem | None
    rows: list[tuple[UploadSessionItem, str | None, str | None]]
    item_key: str
    filename: str
    file_ext: str


@dataclass
class StagedUpload:
    path: Path
    content_hash: str
    size: int


@dataclass
class PersistedUpload:
    item: UploadSessionItem
    document: Document
    deduped: bool
