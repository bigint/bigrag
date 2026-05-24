from __future__ import annotations

import base64
import hashlib
import tempfile
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

import orjson
import sqlalchemy as sa

from bigrag.db.base import Base
from bigrag.db.engine import session_factory
from bigrag.logging import get_logger
from bigrag.services.runtime_settings import all_runtime_values
from bigrag.services.vector_store import vector_store

from .constants import REDACTED
from .target import build_backup_target

logger = get_logger("bigrag.restore")

_RESTORE_BATCH_SIZE = 500


class RestoreError(RuntimeError):
    pass


class RestoreNotEmptyError(RestoreError):
    pass


class RestoreChecksumError(RestoreError):
    pass


class RestoreRedactedError(RestoreError):
    pass


async def restore_backup_job(
    *,
    backup_prefix: str,
    confirm: bool = False,
    overwrite: bool = False,
    restore_vectors: bool = False,
) -> dict[str, Any]:
    if confirm is not True:
        raise RestoreError("restore_backup_job requires confirm=True (destructive operation)")

    values = await all_runtime_values()
    target = build_backup_target(values)
    await target.probe()

    with tempfile.TemporaryDirectory(prefix="bigrag-restore-") as raw_dir:
        temp_dir = Path(raw_dir)
        manifest = orjson.loads(
            await target.read_object(backup_prefix=backup_prefix, path="manifest.json")
        )
        checksums = orjson.loads(
            await target.read_object(backup_prefix=backup_prefix, path="checksums.json")
        )
        objects = _index_checksums(checksums)

        for path in objects:
            dest = temp_dir / path
            await target.download_file(backup_prefix=backup_prefix, path=path, dest=dest)
            _verify_checksum(dest, path, objects[path])

        await _guard_schema_revision(manifest)
        await _guard_empty(overwrite=overwrite)

        table_summary = await _restore_tables(temp_dir, objects)
        vector_summary = await _restore_vectors(temp_dir, objects, restore_vectors=restore_vectors)

    result = {
        "backup_id": manifest.get("backup_id"),
        "snapshot_ts": manifest.get("snapshot_ts"),
        "tables": table_summary,
        "vectors": vector_summary,
    }
    logger.info("restore complete", **{k: v for k, v in result.items() if k != "tables"})
    return result


def _index_checksums(checksums: dict[str, Any]) -> dict[str, str]:
    indexed: dict[str, str] = {}
    for obj in checksums.get("objects", []):
        path = obj.get("path")
        digest = obj.get("sha256")
        if path and digest:
            indexed[path] = digest
    return indexed


def _verify_checksum(dest: Path, path: str, expected: str) -> None:
    digest = hashlib.sha256()
    with dest.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected:
        raise RestoreChecksumError(
            f"Checksum mismatch for {path}: expected {expected}, got {actual}"
        )


async def _guard_schema_revision(manifest: dict[str, Any]) -> None:
    expected = manifest.get("db_revision")
    if not expected:
        return
    async with session_factory()() as session:
        try:
            actual = await session.scalar(
                sa.text("SELECT version_num FROM alembic_version LIMIT 1")
            )
        except Exception:
            actual = None
    if actual is not None and actual != expected:
        raise RestoreError(
            f"Schema revision mismatch: backup={expected}, target={actual}. "
            "Migrate the target to the backup revision before restoring."
        )


async def _guard_empty(*, overwrite: bool) -> None:
    if overwrite:
        return
    async with session_factory()() as session:
        for mapper in Base.registry.mappers:
            table = mapper.local_table
            count = await session.scalar(sa.select(sa.func.count()).select_from(table))
            if int(count or 0) > 0:
                raise RestoreNotEmptyError(
                    f"Target table {table.name} is not empty; pass overwrite=True to replace"
                )


async def _restore_tables(temp_dir: Path, objects: dict[str, str]) -> dict[str, int]:
    summary: dict[str, int] = {}
    ordered = list(Base.metadata.sorted_tables)
    mapper_by_table = {mapper.local_table.name: mapper for mapper in Base.registry.mappers}

    async with session_factory()() as session:
        for table in reversed(ordered):
            await session.execute(sa.delete(table))
        await session.commit()

    for table in ordered:
        path = f"postgres/tables/{table.name}.jsonl"
        if path not in objects:
            continue
        source = temp_dir / path
        if not source.exists():
            continue
        if table.name not in mapper_by_table:
            continue
        inserted = await _insert_table_rows(table, source)
        summary[table.name] = inserted
    return summary


async def _insert_table_rows(table: Any, source: Path) -> int:
    columns = {column.name: column for column in table.columns}
    inserted = 0
    batch: list[dict[str, Any]] = []
    async with session_factory()() as session:
        with source.open("rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw = orjson.loads(line)
                row = _coerce_row(table, columns, raw)
                batch.append(row)
                if len(batch) >= _RESTORE_BATCH_SIZE:
                    await session.execute(sa.insert(table).values(batch))
                    inserted += len(batch)
                    batch = []
            if batch:
                await session.execute(sa.insert(table).values(batch))
                inserted += len(batch)
        await session.commit()
    return inserted


def _coerce_row(table: Any, columns: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for name, value in raw.items():
        column = columns.get(name)
        if column is None:
            continue
        if value == REDACTED:
            if not column.nullable:
                raise RestoreRedactedError(
                    f"Cannot restore redacted non-nullable column {table.name}.{name}; "
                    "this value was not captured in the backup"
                )
            row[name] = None
            continue
        row[name] = _coerce_value(column, value)
    return row


def _coerce_value(column: Any, value: Any) -> Any:
    if value is None:
        return None
    type_name = column.type.__class__.__name__
    if type_name in {"Uuid", "UUID"} and isinstance(value, str):
        return uuid.UUID(value)
    if type_name == "DateTime" and isinstance(value, str):
        return datetime.fromisoformat(value)
    if type_name == "Date" and isinstance(value, str):
        return date.fromisoformat(value)
    if type_name in {"LargeBinary", "BYTEA"} and isinstance(value, str):
        return base64.b64decode(value)
    return value


async def _restore_vectors(
    temp_dir: Path,
    objects: dict[str, str],
    *,
    restore_vectors: bool,
) -> dict[str, Any]:
    collections_path = "vector_store/collections.json"
    if collections_path not in objects:
        return {"restored": False, "reason": "no vector_store metadata in backup"}
    collections = orjson.loads((temp_dir / collections_path).read_bytes())

    summary: dict[str, Any] = {"collections": {}, "restored": True}
    for entry in collections:
        name = entry.get("collection") or entry.get("vector_store_collection")
        if not name:
            continue
        dimension = entry.get("dimension")
        points_path = f"vector_store/points/{name}.jsonl"
        source = temp_dir / points_path
        point_count = await _restore_collection_points(
            name,
            dimension,
            source if points_path in objects and source.exists() else None,
            restore_vectors=restore_vectors,
        )
        summary["collections"][name] = point_count
    return summary


async def _restore_collection_points(
    name: str,
    dimension: int | None,
    source: Path | None,
    *,
    restore_vectors: bool,
) -> dict[str, Any]:
    if dimension:
        await vector_store.create_collection(name, dimension)

    if source is None:
        return {"namespace_created": bool(dimension), "points": 0, "vectors_inserted": False}

    has_vectors, total = _scan_points(source)
    if total == 0:
        return {"namespace_created": bool(dimension), "points": 0, "vectors_inserted": False}

    if not has_vectors:
        if restore_vectors:
            raise RestoreRedactedError(
                f"Collection {name} points have redacted vectors; cannot re-embed during restore"
            )
        return {
            "namespace_created": bool(dimension),
            "points": total,
            "vectors_inserted": False,
            "warning": "vectors redacted in backup; points not re-inserted",
        }

    inserted = await _insert_points(name, source)
    return {
        "namespace_created": bool(dimension),
        "points": total,
        "vectors_inserted": True,
        "inserted": inserted,
    }


def _scan_points(source: Path) -> tuple[bool, int]:
    has_vectors = True
    total = 0
    with source.open("rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            record = orjson.loads(line)
            vector = record.get("vector")
            if vector == REDACTED or vector is None:
                has_vectors = False
    return has_vectors, total


async def _insert_points(name: str, source: Path) -> int:
    inserted = 0
    ids: list[str] = []
    document_ids: list[str] = []
    chunk_indices: list[int] = []
    texts: list[str] = []
    embeddings: list[list[float]] = []
    metadata: list[dict] = []

    async def flush() -> int:
        if not ids:
            return 0
        count = await vector_store.insert(
            name,
            list(ids),
            list(document_ids),
            list(chunk_indices),
            list(texts),
            list(embeddings),
            list(metadata),
        )
        ids.clear()
        document_ids.clear()
        chunk_indices.clear()
        texts.clear()
        embeddings.clear()
        metadata.clear()
        return count

    with source.open("rb") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = orjson.loads(line)
            payload = record.get("payload") or {}
            public_id = payload.get("id") or record.get("id")
            ids.append(str(public_id))
            document_ids.append(str(payload.get("document_id") or ""))
            chunk_indices.append(int(payload.get("chunk_index") or 0))
            texts.append(str(payload.get("text") or ""))
            embeddings.append([float(component) for component in record.get("vector") or []])
            metadata.append(
                {
                    k: v
                    for k, v in payload.items()
                    if k not in {"id", "document_id", "chunk_index", "text"}
                }
            )
            if len(ids) >= _RESTORE_BATCH_SIZE:
                inserted += await flush()
    inserted += await flush()
    return inserted
