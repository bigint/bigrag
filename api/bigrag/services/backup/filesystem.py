from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

import orjson
from fastapi.encoders import jsonable_encoder
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from bigrag.db.base import Base

from .constants import BACKUP_ROOT


def _write_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dialect = postgresql.dialect()
    with path.open("w", encoding="utf-8") as f:
        for table in Base.metadata.sorted_tables:
            f.write(f"{CreateTable(table).compile(dialect=dialect)};\n\n")
            for index in table.indexes:
                f.write(f"{CreateIndex(index).compile(dialect=dialect)};\n\n")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(jsonable_encoder(value), option=orjson.OPT_INDENT_2) + b"\n")


def _readable_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, list | tuple):
        return [_readable_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _readable_value(item) for key, item in value.items()}
    return jsonable_encoder(value)


def _file_stats(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def _backup_prefix(base_prefix: str, job_id: uuid.UUID) -> str:
    parts = [part for part in (base_prefix, BACKUP_ROOT, str(job_id)) if part]
    return "/".join(parts)
