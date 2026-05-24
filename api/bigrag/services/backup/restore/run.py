from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any

import orjson
import sqlalchemy as sa

from bigrag.db.base import Base
from bigrag.db.engine import session_factory
from bigrag.logging import get_logger
from bigrag.services.backup.restore.coerce import (
    RestoreChecksumError,
    RestoreError,
    RestoreNotEmptyError,
)
from bigrag.services.backup.restore.tables import _restore_tables
from bigrag.services.backup.restore.vectors import _restore_vectors
from bigrag.services.backup.target import build_backup_target
from bigrag.services.runtime_settings import all_runtime_values

logger = get_logger("bigrag.restore")


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
