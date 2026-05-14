from __future__ import annotations

import asyncio
import base64
import hashlib
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import orjson
import sqlalchemy as sa
from fastapi.encoders import jsonable_encoder
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from bigrag import __version__
from bigrag.db.base import Base
from bigrag.db.engine import session_factory
from bigrag.db.models import (
    AuditLog,
    BackupJob,
    Collection,
    ConnectorSyncJob,
    Document,
    EmbeddingCache,
)
from bigrag.logging import get_logger
from bigrag.services.maintenance import acquire_backup_lock, release_backup_lock
from bigrag.services.queue import ingestion_queue
from bigrag.services.runtime_settings import all_runtime_values
from bigrag.services.storage import get_storage
from bigrag.services.vector_store import vector_store

logger = get_logger("bigrag.backup")

BACKUP_FORMAT_VERSION = 1
BACKUP_ROOT = "backups"
REDACTED = "[REDACTED]"
_SENSITIVE_COLUMN_NAMES = frozenset(
    {
        "access_token",
        "api_key",
        "client_secret",
        "embedding_api_key",
        "key_hash",
        "password_hash",
        "qdrant_api_key",
        "refresh_token",
        "reranking_api_key",
        "secret",
        "secret_value",
        "session_token",
        "token_hash",
        "vector",
    }
)


@dataclass
class UploadedObject:
    key: str
    path: str
    bytes: int
    sha256: str


@dataclass
class BackupUploadStats:
    objects: list[UploadedObject] = field(default_factory=list)
    bytes: int = 0

    @property
    def object_count(self) -> int:
        return len(self.objects)

    def add(self, obj: UploadedObject) -> None:
        self.objects.append(obj)
        self.bytes += obj.bytes


class BackupConfigError(RuntimeError):
    pass


class S3BackupTarget:
    def __init__(self, values: dict[str, Any]) -> None:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise BackupConfigError("boto3 is required for S3-compatible backups") from exc
        bucket = values.get("backup_s3_bucket") or ""
        if not bucket:
            raise BackupConfigError("backup_s3_bucket is required")
        force_path_style = bool(values.get("backup_s3_force_path_style"))
        kwargs: dict[str, Any] = {
            "endpoint_url": values.get("backup_s3_endpoint_url"),
            "region_name": values.get("backup_s3_region") or "us-east-1",
            "config": Config(s3={"addressing_style": "path" if force_path_style else "auto"}),
        }
        access_key_id = values.get("backup_s3_access_key_id")
        secret_access_key = values.get("backup_s3_secret_access_key")
        if access_key_id and secret_access_key:
            kwargs["aws_access_key_id"] = access_key_id
            kwargs["aws_secret_access_key"] = secret_access_key
        self.client = boto3.client("s3", **kwargs)
        self.bucket = bucket
        self.endpoint_url = values.get("backup_s3_endpoint_url")
        self.region = values.get("backup_s3_region") or "us-east-1"
        self.prefix = str(values.get("backup_s3_prefix") or "").strip("/")

    def object_key(self, backup_prefix: str, path: str) -> str:
        clean = path.lstrip("/")
        return f"{backup_prefix}/{clean}"

    async def probe(self) -> None:
        await asyncio.to_thread(
            self.client.list_objects_v2,
            Bucket=self.bucket,
            Prefix=self.prefix,
            MaxKeys=1,
        )

    async def upload_file(self, source: Path, *, backup_prefix: str, path: str) -> UploadedObject:
        object_key = self.object_key(backup_prefix, path)
        size, digest = await asyncio.to_thread(_file_stats, source)
        await asyncio.to_thread(
            self.client.upload_file,
            str(source),
            self.bucket,
            object_key,
        )
        return UploadedObject(key=object_key, path=path, bytes=size, sha256=digest)


def build_backup_target(values: dict[str, Any]) -> S3BackupTarget:
    return S3BackupTarget(values)


async def test_backup_target(values: dict[str, Any]) -> None:
    target = build_backup_target(values)
    await target.probe()


async def create_backup_job(*, label: str, created_by: uuid.UUID | None) -> BackupJob:
    async with session_factory()() as session:
        active = await session.scalar(
            sa.select(BackupJob)
            .where(BackupJob.status.in_(("pending", "running")))
            .order_by(BackupJob.created_at.desc())
            .limit(1)
        )
        if active is not None:
            raise BackupConfigError("A backup is already pending or running")
        job = BackupJob(label=label.strip(), created_by=created_by)
        session.add(job)
        await session.commit()
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

    with tempfile.TemporaryDirectory(prefix=f"bigrag-backup-{job_id}-") as raw_dir:
        temp_dir = Path(raw_dir)
        schema_path = temp_dir / "postgres" / "schema.sql"
        await asyncio.to_thread(_write_schema, schema_path)
        await _upload(target, stats, backup_prefix, "postgres/schema.sql", schema_path)
        await _update_job(
            job_id,
            progress=0.18,
            object_count=stats.object_count,
            byte_count=stats.bytes,
        )

        table_counts = await _export_tables(temp_dir)
        for table_name in sorted(table_counts):
            source = temp_dir / "postgres" / "tables" / f"{table_name}.jsonl"
            await _upload(
                target,
                stats,
                backup_prefix,
                f"postgres/tables/{table_name}.jsonl",
                source,
            )
        await _update_job(
            job_id,
            progress=0.42,
            object_count=stats.object_count,
            byte_count=stats.bytes,
        )

        vector_counts = await _export_vector_store(temp_dir)
        await _upload(
            target,
            stats,
            backup_prefix,
            "vector_store/collections.json",
            temp_dir / "vector_store" / "collections.json",
        )
        for collection_name in sorted(vector_counts):
            source = temp_dir / "vector_store" / "points" / f"{collection_name}.jsonl"
            await _upload(
                target,
                stats,
                backup_prefix,
                f"vector_store/points/{collection_name}.jsonl",
                source,
            )
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
                await _upload(
                    target,
                    stats,
                    backup_prefix,
                    source.relative_to(temp_dir).as_posix(),
                    source,
                )
        await _update_job(
            job_id,
            progress=0.88,
            object_count=stats.object_count,
            byte_count=stats.bytes,
        )

        checksums_path = temp_dir / "checksums.json"
        _write_json(
            checksums_path,
            {
                "backup_id": str(job_id),
                "generated_at": datetime.now(UTC).isoformat(),
                "objects": [obj.__dict__ for obj in stats.objects],
            },
        )
        await _upload(target, stats, backup_prefix, "checksums.json", checksums_path)
        manifest = _manifest(
            job_id=job_id,
            target=target,
            backup_prefix=backup_prefix,
            table_counts=table_counts,
            vector_counts=vector_counts,
            upload_count=upload_count,
            stats=stats,
        )
        manifest_path = temp_dir / "manifest.json"
        _write_json(manifest_path, manifest)
        await _upload(target, stats, backup_prefix, "manifest.json", manifest_path)

    manifest["object_count"] = stats.object_count
    manifest["byte_count"] = stats.bytes
    await _complete_job(
        job_id,
        destination_prefix=backup_prefix,
        object_count=stats.object_count,
        byte_count=stats.bytes,
        manifest=manifest,
    )


async def _wait_for_ingestion_drain(job_id: uuid.UUID) -> None:
    while True:
        stats = await ingestion_queue.stats
        processing = int(stats.get("processing") or 0)
        if processing <= 0:
            return
        await _update_job(job_id, progress=0.08)
        await asyncio.sleep(1)


async def _wait_for_connector_sync_drain(job_id: uuid.UUID) -> None:
    while True:
        async with session_factory()() as session:
            running = await session.scalar(
                sa.select(sa.func.count())
                .select_from(ConnectorSyncJob)
                .where(ConnectorSyncJob.status == "running")
            )
        if int(running or 0) <= 0:
            return
        await _update_job(job_id, progress=0.06)
        await asyncio.sleep(1)


async def _export_tables(temp_dir: Path) -> dict[str, int]:
    out_dir = temp_dir / "postgres" / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for mapper in sorted(Base.registry.mappers, key=lambda item: item.local_table.name):
        model = mapper.class_
        table_name = mapper.local_table.name
        count = 0
        target = out_dir / f"{table_name}.jsonl"
        async with session_factory()() as session:
            result = await session.stream_scalars(sa.select(model))
            with target.open("wb") as f:
                async for row in result:
                    f.write(orjson.dumps(_row_payload(row, mapper)) + b"\n")
                    count += 1
        counts[table_name] = count
    return counts


def _row_payload(row: Any, mapper: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for attr in mapper.column_attrs:
        column = attr.columns[0]
        value = getattr(row, attr.key)
        if _redact_column(row, column):
            payload[column.name] = REDACTED if value is not None else None
        elif isinstance(row, EmbeddingCache) and column.name == "vector":
            payload[column.name] = REDACTED
        else:
            payload[column.name] = _readable_value(value)
    return payload


def _redact_column(row: Any, column: Any) -> bool:
    if column.name in _SENSITIVE_COLUMN_NAMES:
        return True
    if isinstance(row, EmbeddingCache) and column.name == "vector":
        return True
    return column.type.__class__.__name__ == "EncryptedString"


async def _export_vector_store(temp_dir: Path) -> dict[str, int]:
    points_dir = temp_dir / "vector_store" / "points"
    points_dir.mkdir(parents=True, exist_ok=True)
    collections_meta = []
    counts: dict[str, int] = {}
    async with session_factory()() as session:
        collections = (
            await session.scalars(sa.select(Collection).order_by(Collection.name.asc()))
        ).all()
    for collection in collections:
        points = await vector_store.export_collection_points(collection.name, with_vectors=False)
        exists = bool(points) or collection.document_count == 0
        count = len(points)
        target = points_dir / f"{collection.name}.jsonl"
        with target.open("wb") as f:
            for point in points:
                f.write(orjson.dumps(_point_payload(point)) + b"\n")
        if not exists and collection.document_count > 0:
            raise RuntimeError(f"Vector store collection missing: {collection.name}")
        counts[collection.name] = count
        collections_meta.append(
            {
                "collection": collection.name,
                "provider": vector_store.provider,
                "vector_store_collection": collection.name,
                "exists": exists,
                "points": count,
            }
        )
    _write_json(temp_dir / "vector_store" / "collections.json", collections_meta)
    return counts


def _point_payload(point: Any) -> dict[str, Any]:
    if isinstance(point, dict):
        return {
            "id": str(point.get("id", "")),
            "payload": _readable_value(point.get("payload") or {}),
            "vector": REDACTED,
        }
    return {
        "id": str(getattr(point, "id", "")),
        "payload": _readable_value(getattr(point, "payload", {}) or {}),
        "vector": REDACTED,
    }


async def _export_uploads(temp_dir: Path) -> int:
    storage = get_storage()
    async with session_factory()() as session:
        docs = (
            await session.scalars(
                sa.select(Document)
                .where(Document.file_path != "")
                .order_by(Document.collection_id.asc(), Document.id.asc())
            )
        ).all()
    count = 0
    for doc in docs:
        target = temp_dir / "uploads" / doc.file_path
        await storage.write_to_path(doc.file_path, target)
        count += 1
    return count


async def _upload(
    target: S3BackupTarget,
    stats: BackupUploadStats,
    backup_prefix: str,
    path: str,
    source: Path,
) -> None:
    stats.add(await target.upload_file(source, backup_prefix=backup_prefix, path=path))


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


def _manifest(
    *,
    job_id: uuid.UUID,
    target: S3BackupTarget,
    backup_prefix: str,
    table_counts: dict[str, int],
    vector_counts: dict[str, int],
    upload_count: int,
    stats: BackupUploadStats,
) -> dict[str, Any]:
    return {
        "backup_id": str(job_id),
        "format_version": BACKUP_FORMAT_VERSION,
        "app_version": __version__,
        "generated_at": datetime.now(UTC).isoformat(),
        "encryption": "redacted",
        "redaction": {
            "secret_columns": True,
            "embedding_cache_vectors": True,
            "vector_store_vectors": True,
            "raw_uploads": False,
        },
        "destination": {
            "bucket": target.bucket,
            "endpoint_url": target.endpoint_url,
            "region": target.region,
            "prefix": backup_prefix,
        },
        "tables": table_counts,
        "vector_store": {"provider": vector_store.provider},
        "vectors": vector_counts,
        "uploads": {"files": upload_count},
        "object_count": stats.object_count,
        "byte_count": stats.bytes,
    }


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
