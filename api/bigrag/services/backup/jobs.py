from __future__ import annotations

import asyncio
import tempfile
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson
import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import AuditLog, BackupJob, ConnectorSyncJob
from bigrag.logging import get_logger
from bigrag.services.maintenance import acquire_backup_lock, release_backup_lock
from bigrag.services.queue import ingestion_queue
from bigrag.services.runtime_settings import all_runtime_values

from .exporters import _export_tables, _export_uploads, _export_vector_store
from .filesystem import _backup_prefix, _write_json, _write_schema
from .manifest import _manifest
from .target import BackupConfigError, BackupUploadStats, S3BackupTarget, build_backup_target

logger = get_logger("bigrag.backup")


async def create_backup_job(*, label: str, created_by: uuid.UUID | None) -> BackupJob:
    async with session_factory()() as session:
        async with session.begin():
            active = await session.scalar(
                sa.select(BackupJob)
                .where(BackupJob.status.in_(("pending", "running")))
                .order_by(BackupJob.created_at.desc())
                .limit(1)
                .with_for_update()
            )
            if active is not None:
                raise BackupConfigError("A backup is already pending or running")
            job = BackupJob(label=label.strip(), created_by=created_by)
            session.add(job)
        await session.refresh(job)
        return job


async def run_backup_job(job_id: str) -> None:
    owner_id = uuid.UUID(job_id)
    try:
        acquired = await acquire_backup_lock(owner_id)
        if not acquired:
            await _fail_job(owner_id, "Another maintenance lock is active")
            return
        await _mark_job_running(owner_id)
        await _wait_for_connector_sync_drain(owner_id)
        await _wait_for_ingestion_drain(owner_id)
        await _run_locked_backup(owner_id)
    except Exception as exc:
        logger.exception("backup failed", job_id=job_id, error=str(exc))
        await _fail_job(owner_id, str(exc))
    finally:
        await release_backup_lock(owner_id)


async def _run_locked_backup(job_id: uuid.UUID) -> None:
    values = await all_runtime_values()
    target = build_backup_target(values)
    await target.probe()
    backup_prefix = _backup_prefix(target.prefix, job_id)
    stats = BackupUploadStats()
    table_counts: dict[str, int] = {}
    vector_counts: dict[str, int] = {}
    upload_count = 0
    db_revision = await _read_alembic_revision()

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

            table_counts = await _export_tables(temp_dir)
            for table_name in sorted(table_counts):
                source = temp_dir / "postgres" / "tables" / f"{table_name}.jsonl"
                await upload(f"postgres/tables/{table_name}.jsonl", source)
            await _update_job(
                job_id,
                progress=0.42,
                object_count=stats.object_count,
                byte_count=stats.bytes,
            )

            vector_counts = await _export_vector_store(temp_dir)
            await upload(
                "vector_store/collections.json",
                temp_dir / "vector_store" / "collections.json",
            )
            for collection_name in sorted(vector_counts):
                source = temp_dir / "vector_store" / "points" / f"{collection_name}.jsonl"
                await upload(f"vector_store/points/{collection_name}.jsonl", source)
            await _update_job(
                job_id,
                progress=0.68,
                object_count=stats.object_count,
                byte_count=stats.bytes,
            )

            upload_count = await _export_uploads(temp_dir)
            upload_root = temp_dir / "uploads"
            for source in sorted(upload_root.rglob("*")):
                if source.is_file():
                    await upload(source.relative_to(temp_dir).as_posix(), source)
            await _update_job(
                job_id,
                progress=0.88,
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
            upload_count=upload_count,
            stats=stats,
            db_revision=db_revision,
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


async def _mark_job_running(job_id: uuid.UUID) -> None:
    await _update_job(job_id, status="running", progress=0.03, started_at=datetime.now(UTC))
    await _insert_audit(job_id, "backup.start", {})


async def _complete_job(
    job_id: uuid.UUID,
    *,
    destination_prefix: str,
    object_count: int,
    byte_count: int,
    manifest: dict[str, Any],
) -> None:
    await _update_job(
        job_id,
        status="succeeded",
        progress=1.0,
        destination_prefix=destination_prefix,
        object_count=object_count,
        byte_count=byte_count,
        manifest=manifest,
        completed_at=datetime.now(UTC),
    )
    await _insert_audit(job_id, "backup.succeeded", {"destination_prefix": destination_prefix})


async def _fail_job(job_id: uuid.UUID, message: str) -> None:
    await _update_job(
        job_id,
        status="failed",
        error_message=message,
        completed_at=datetime.now(UTC),
    )
    await _insert_audit(job_id, "backup.failed", {"error": message})


async def _update_job(job_id: uuid.UUID, **values: Any) -> None:
    async with session_factory()() as session:
        values["updated_at"] = sa.func.now()
        await session.execute(sa.update(BackupJob).where(BackupJob.id == job_id).values(**values))
        await session.commit()


async def _insert_audit(job_id: uuid.UUID, action: str, metadata: dict[str, Any]) -> None:
    async with session_factory()() as session:
        job = await session.get(BackupJob, job_id)
        session.add(
            AuditLog(
                actor_id=job.created_by if job else None,
                actor_email=None,
                api_key_id=None,
                action=action,
                resource_type="backup_job",
                resource_id=str(job_id),
                meta=metadata,
                ip=None,
                user_agent=None,
            )
        )
        await session.commit()
