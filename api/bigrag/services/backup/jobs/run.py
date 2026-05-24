from __future__ import annotations

import asyncio
import tempfile
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import orjson
import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import ConnectorSyncJob
from bigrag.logging import get_logger
from bigrag.services.backup.exporters import _export_tables, _export_vector_store
from bigrag.services.backup.filesystem import _backup_prefix, _write_json, _write_schema
from bigrag.services.backup.jobs.events import (
    _complete_job,
    _fail_job,
    _mark_job_running,
    _update_job,
)
from bigrag.services.backup.jobs.lock import (
    _BACKUP_LOCK_TTL_SECONDS,
    _renew_lock_until_cancelled,
    _set_lock_ttl,
)
from bigrag.services.backup.manifest import _manifest
from bigrag.services.backup.target import (
    BackupConfigError,
    BackupUploadStats,
    S3BackupTarget,
    build_backup_target,
)
from bigrag.services.maintenance import acquire_backup_lock, release_backup_lock
from bigrag.services.queue import ingestion_queue
from bigrag.services.runtime_settings import all_runtime_values

logger = get_logger("bigrag.backup")

_VECTOR_EXPORT_TIMEOUT_SECONDS = 3600


async def run_backup_job(job_id: str) -> None:
    owner_id = uuid.UUID(job_id)
    renewer: asyncio.Task[None] | None = None
    try:
        acquired = await acquire_backup_lock(owner_id)
        if not acquired:
            await _fail_job(owner_id, "Another maintenance lock is active")
            return
        await _set_lock_ttl(owner_id, _BACKUP_LOCK_TTL_SECONDS)
        renewer = asyncio.create_task(_renew_lock_until_cancelled(owner_id))
        await _mark_job_running(owner_id)
        await _wait_for_connector_sync_drain(owner_id)
        await _wait_for_ingestion_drain(owner_id)
        await _run_locked_backup(owner_id)
    except Exception as exc:
        logger.exception("backup failed", job_id=job_id, error=str(exc))
        await _fail_job(owner_id, str(exc))
    finally:
        if renewer is not None:
            renewer.cancel()
            try:
                await renewer
            except (asyncio.CancelledError, Exception):
                pass
        await release_backup_lock(owner_id)


async def _run_locked_backup(job_id: uuid.UUID) -> None:
    values = await all_runtime_values()
    target = build_backup_target(values)
    await target.probe()
    backup_prefix = _backup_prefix(target.prefix, job_id)
    stats = BackupUploadStats()
    table_counts: dict[str, int] = {}
    vector_counts: dict[str, int] = {}
    db_revision = await _read_alembic_revision()
    snapshot_ts = datetime.now(UTC)

    with tempfile.TemporaryDirectory(prefix=f"bigrag-backup-{job_id}-") as raw_dir:
        temp_dir = Path(raw_dir)
        checksums_path = temp_dir / "checksums.json"
        with checksums_path.open("wb") as checksums_file:
            checksums_file.write(
                b'{"backup_id": "'
                + str(job_id).encode()
                + b'", "generated_at": "'
                + datetime.now(UTC).isoformat().encode()
                + b'", "objects": [\n'
            )
            first_object = [True]

            async def upload(path: str, source: Path) -> None:
                obj = await target.upload_file(source, backup_prefix=backup_prefix, path=path)
                stats.add(obj)
                if not first_object[0]:
                    checksums_file.write(b",\n")
                first_object[0] = False
                checksums_file.write(orjson.dumps(asdict(obj)))

            schema_path = temp_dir / "postgres" / "schema.sql"
            await asyncio.to_thread(_write_schema, schema_path)
            await upload("postgres/schema.sql", schema_path)
            await _update_job(
                job_id,
                progress=0.18,
                object_count=stats.object_count,
                byte_count=stats.bytes,
            )

            table_counts = await _export_tables(temp_dir, snapshot_ts)
            for table_name in sorted(table_counts):
                source = temp_dir / "postgres" / "tables" / f"{table_name}.jsonl"
                await upload(f"postgres/tables/{table_name}.jsonl", source)
            await _update_job(
                job_id,
                progress=0.42,
                object_count=stats.object_count,
                byte_count=stats.bytes,
            )

            vector_counts = await asyncio.wait_for(
                _export_vector_store(temp_dir, snapshot_ts),
                timeout=_VECTOR_EXPORT_TIMEOUT_SECONDS,
            )
            await upload(
                "vector_store/collections.json",
                temp_dir / "vector_store" / "collections.json",
            )
            for collection_name in sorted(vector_counts):
                source = temp_dir / "vector_store" / "points" / f"{collection_name}.jsonl"
                await upload(f"vector_store/points/{collection_name}.jsonl", source)
            await _update_job(
                job_id,
                progress=0.82,
                object_count=stats.object_count,
                byte_count=stats.bytes,
            )

            checksums_file.write(b"\n]}\n")

        await upload_standalone(target, stats, backup_prefix, "checksums.json", checksums_path)
        manifest = _manifest(
            job_id=job_id,
            target=target,
            backup_prefix=backup_prefix,
            table_counts=table_counts,
            vector_counts=vector_counts,
            stats=stats,
            db_revision=db_revision,
            snapshot_ts=snapshot_ts,
        )
        manifest_path = temp_dir / "manifest.json"
        _write_json(manifest_path, manifest)
        await upload_standalone(target, stats, backup_prefix, "manifest.json", manifest_path)

    manifest["object_count"] = stats.object_count
    manifest["byte_count"] = stats.bytes
    await _complete_job(
        job_id,
        destination_prefix=backup_prefix,
        object_count=stats.object_count,
        byte_count=stats.bytes,
        manifest=manifest,
    )


async def upload_standalone(
    target: S3BackupTarget,
    stats: BackupUploadStats,
    backup_prefix: str,
    path: str,
    source: Path,
) -> None:
    stats.add(await target.upload_file(source, backup_prefix=backup_prefix, path=path))


async def _read_alembic_revision() -> str | None:
    try:
        async with session_factory()() as session:
            return await session.scalar(sa.text("SELECT version_num FROM alembic_version LIMIT 1"))
    except Exception:
        return None


async def _wait_for_ingestion_drain(job_id: uuid.UUID, max_wait_seconds: int = 1800) -> None:
    deadline = asyncio.get_event_loop().time() + max_wait_seconds
    while True:
        stats = await ingestion_queue.stats
        processing = int(stats.get("processing") or 0)
        if processing <= 0:
            return
        if asyncio.get_event_loop().time() >= deadline:
            raise BackupConfigError(
                f"Timed out waiting for ingestion drain after {max_wait_seconds}s"
            )
        await _update_job(job_id, progress=0.08)
        await asyncio.sleep(1)


async def _wait_for_connector_sync_drain(job_id: uuid.UUID, max_wait_seconds: int = 1800) -> None:
    deadline = asyncio.get_event_loop().time() + max_wait_seconds
    while True:
        async with session_factory()() as session:
            running = await session.scalar(
                sa.select(sa.func.count())
                .select_from(ConnectorSyncJob)
                .where(ConnectorSyncJob.status == "running")
            )
        if int(running or 0) <= 0:
            return
        if asyncio.get_event_loop().time() >= deadline:
            raise BackupConfigError(
                f"Timed out waiting for connector sync drain after {max_wait_seconds}s"
            )
        await _update_job(job_id, progress=0.06)
        await asyncio.sleep(1)
