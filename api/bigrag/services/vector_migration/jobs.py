from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import AuditLog, Collection, ConnectorSyncJob, VectorMigrationJob
from bigrag.logging import get_logger
from bigrag.services import collection_cache
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.maintenance import (
    acquire_maintenance_lock,
    active_lock,
    release_maintenance_lock,
)
from bigrag.services.queue import ingestion_queue
from bigrag.services.retrieval import invalidate_collection_query_cache
from bigrag.services.runtime_settings import get_value
from bigrag.services.vector_store import vector_store
from bigrag.services.vector_store._util import validate_provider
from bigrag.services.vector_store.base import _FIXED_PAYLOAD_FIELDS

logger = get_logger("bigrag.vector_migration")

ACTIVE_STATUSES = ("pending", "running")


class VectorMigrationError(RuntimeError):
    pass


class VectorMigrationConflictError(VectorMigrationError):
    pass


async def create_vector_migration_job(
    *,
    collection_name: str,
    target_provider: str,
    created_by: uuid.UUID | None,
) -> VectorMigrationJob:
    target = validate_provider(target_provider)
    lock = await active_lock()
    if lock is not None:
        raise VectorMigrationConflictError(f"Instance maintenance active: {lock.reason}")
    if target not in vector_store.configured_providers:
        raise VectorMigrationError(f"{target} vector store is not configured")
    async with session_factory()() as session:
        async with session.begin():
            active = await session.scalar(
                sa.select(VectorMigrationJob)
                .where(VectorMigrationJob.status.in_(ACTIVE_STATUSES))
                .order_by(VectorMigrationJob.created_at.desc())
                .limit(1)
                .with_for_update()
            )
            if active is not None:
                raise VectorMigrationConflictError(
                    "A vector migration is already pending or running"
                )
            collection = await session.scalar(
                sa.select(Collection).where(Collection.name == collection_name).with_for_update()
            )
            if collection is None:
                raise VectorMigrationError("Collection not found")
            source = validate_provider(collection.vector_store_provider)
            if source == target:
                raise VectorMigrationConflictError("Collection already uses that vector provider")
            job = VectorMigrationJob(
                collection_id=collection.id,
                collection_name=collection.name,
                source_provider=source,
                target_provider=target,
                created_by=created_by,
            )
            session.add(job)
        await session.refresh(job)
        return job


async def run_vector_migration_job(job_id: str) -> None:
    owner_id = uuid.UUID(job_id)
    locked = False
    try:
        job = await _get_job(owner_id)
        if job is None:
            return
        if job.status != "pending":
            return
        locked = await acquire_maintenance_lock(
            owner_id,
            reason=f"vector migration for {job.collection_name}",
            metadata={
                "collection": job.collection_name,
                "source_provider": job.source_provider,
                "target_provider": job.target_provider,
            },
        )
        if not locked:
            await _fail_job(owner_id, "Another maintenance lock is active")
            return
        await _mark_running(owner_id)
        await _wait_for_connector_sync_drain(owner_id)
        await _wait_for_ingestion_drain(owner_id)
        await _run_locked_migration(owner_id)
    except Exception as exc:
        logger.exception("vector migration failed", job_id=job_id, error=str(exc))
        await _fail_job(owner_id, sanitize_message_text(str(exc)) or "Vector migration failed")
    finally:
        if locked:
            await release_maintenance_lock(owner_id)


async def _run_locked_migration(job_id: uuid.UUID) -> None:
    job, collection = await _load_job_and_collection(job_id)
    if job is None:
        return
    if collection is None:
        await _fail_job(job_id, "Collection not found")
        return
    source = validate_provider(job.source_provider)
    target = validate_provider(job.target_provider)
    cutover_done = False
    copied = 0
    try:
        if collection.vector_store_provider != source:
            raise VectorMigrationError(
                "Collection vector provider changed before migration started"
            )
        await _update_job(job_id, phase="provisioning", progress=0.2)
        await vector_store.delete_collection(collection.name, provider=target)
        await vector_store.create_collection(
            collection.name,
            collection.dimension,
            index_type=collection.index_type,
            tenant_field=collection.tenant_field,
            provider=target,
        )
        copied = await _copy_points(job_id, collection.name, source, target)
        await _update_job(
            job_id,
            phase="verifying",
            progress=0.86,
            copied_points=copied,
            total_points=copied,
        )
        target_count = 0 if copied == 0 else await _count_points(collection.name, target)
        if target_count != copied:
            raise VectorMigrationError(
                f"Target point count mismatch: copied {copied}, target has {target_count}"
            )
        await _cutover_collection(job_id, collection.id, collection.name, source, target)
        cutover_done = True
        await _update_job(
            job_id,
            phase="cleanup",
            progress=0.94,
            copied_points=copied,
            total_points=copied,
        )
        await vector_store.delete_collection(collection.name, provider=source)
        await _complete_job(job_id, copied)
    except Exception as exc:
        message = sanitize_message_text(str(exc)) or "Vector migration failed"
        if not cutover_done:
            try:
                await vector_store.delete_collection(collection.name, provider=target)
            except Exception as cleanup_exc:
                logger.warning(
                    "partial vector migration cleanup failed",
                    collection=collection.name,
                    target_provider=target,
                    error=str(cleanup_exc),
                )
        await _fail_job(
            job_id,
            message,
            phase="cleanup_failed" if cutover_done else "failed",
            copied_points=copied,
            total_points=copied or None,
        )


async def _copy_points(
    job_id: uuid.UUID,
    collection: str,
    source: str,
    target: str,
) -> int:
    batch_size = max(1, min(int(await get_value("ingestion_batch_size")), 1000))
    copied = 0
    batch: list[dict[str, Any]] = []
    await _update_job(job_id, phase="copying", progress=0.32)
    async for point in vector_store.iter_collection_points(
        collection,
        with_vectors=True,
        provider=source,
    ):
        batch.append(_normalise_point(point))
        if len(batch) >= batch_size:
            copied += await _insert_batch(collection, target, batch)
            batch.clear()
            await _update_job(
                job_id,
                copied_points=copied,
                progress=min(0.84, 0.34 + copied / (copied + batch_size) * 0.48),
            )
    if batch:
        copied += await _insert_batch(collection, target, batch)
    await _update_job(job_id, copied_points=copied, progress=0.84)
    return copied


def _normalise_point(point: dict[str, Any]) -> dict[str, Any]:
    payload = dict(point.get("payload") or {})
    vector = point.get("vector")
    if vector is None:
        raise VectorMigrationError("Source point is missing its vector")
    public_id = str(payload.get("id") or point.get("id") or "")
    if not public_id:
        raise VectorMigrationError("Source point is missing its id")
    return {
        "id": public_id,
        "document_id": str(payload.get("document_id") or ""),
        "chunk_index": int(payload.get("chunk_index") or 0),
        "text": str(payload.get("text") or ""),
        "vector": vector,
        "metadata": {
            k: v
            for k, v in payload.items()
            if k not in _FIXED_PAYLOAD_FIELDS and v is not None
        },
    }


async def _insert_batch(
    collection: str,
    target: str,
    batch: list[dict[str, Any]],
) -> int:
    return await vector_store.insert(
        collection=collection,
        ids=[item["id"] for item in batch],
        document_ids=[item["document_id"] for item in batch],
        chunk_indices=[item["chunk_index"] for item in batch],
        texts=[item["text"] for item in batch],
        embeddings=[item["vector"] for item in batch],
        metadata=[item["metadata"] for item in batch],
        provider=target,
    )


async def _count_points(collection: str, provider: str) -> int:
    count = 0
    async for _point in vector_store.iter_collection_points(
        collection,
        with_vectors=False,
        provider=provider,
    ):
        count += 1
    return count


async def _cutover_collection(
    job_id: uuid.UUID,
    collection_id: uuid.UUID,
    collection_name: str,
    source: str,
    target: str,
) -> None:
    await _update_job(job_id, phase="cutover", progress=0.9)
    async with session_factory()() as session:
        async with session.begin():
            collection = await session.scalar(
                sa.select(Collection).where(Collection.id == collection_id).with_for_update()
            )
            if collection is None:
                raise VectorMigrationError("Collection not found during cutover")
            if collection.vector_store_provider != source:
                raise VectorMigrationError("Collection vector provider changed during migration")
            collection.vector_store_provider = target
        await collection_cache.invalidate(collection_name)
        await invalidate_collection_query_cache(collection_name)


async def _wait_for_ingestion_drain(job_id: uuid.UUID, max_wait_seconds: int = 1800) -> None:
    deadline = asyncio.get_event_loop().time() + max_wait_seconds
    while True:
        stats = await ingestion_queue.stats
        processing = int(stats.get("processing") or 0)
        if processing <= 0:
            return
        if asyncio.get_event_loop().time() >= deadline:
            raise VectorMigrationError(
                f"Timed out waiting for ingestion drain after {max_wait_seconds}s"
            )
        await _update_job(job_id, phase="draining", progress=0.12)
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
            raise VectorMigrationError(
                f"Timed out waiting for connector sync drain after {max_wait_seconds}s"
            )
        await _update_job(job_id, phase="draining", progress=0.08)
        await asyncio.sleep(1)


async def _load_job_and_collection(
    job_id: uuid.UUID,
) -> tuple[VectorMigrationJob | None, Collection | None]:
    async with session_factory()() as session:
        job = await session.get(VectorMigrationJob, job_id)
        if job is None:
            return None, None
        collection = await session.scalar(
            sa.select(Collection).where(Collection.name == job.collection_name)
        )
        return job, collection


async def _get_job(job_id: uuid.UUID) -> VectorMigrationJob | None:
    async with session_factory()() as session:
        return await session.get(VectorMigrationJob, job_id)


async def _mark_running(job_id: uuid.UUID) -> None:
    await _update_job(
        job_id,
        status="running",
        phase="draining",
        progress=0.04,
        started_at=datetime.now(UTC),
    )
    await _insert_audit(job_id, "vector_migration.start", {})


async def _complete_job(job_id: uuid.UUID, copied_points: int) -> None:
    await _update_job(
        job_id,
        status="succeeded",
        phase="complete",
        progress=1.0,
        copied_points=copied_points,
        total_points=copied_points,
        completed_at=datetime.now(UTC),
    )
    await _insert_audit(job_id, "vector_migration.succeeded", {"copied_points": copied_points})


async def _fail_job(
    job_id: uuid.UUID,
    message: str,
    *,
    phase: str = "failed",
    copied_points: int | None = None,
    total_points: int | None = None,
) -> None:
    values: dict[str, Any] = {
        "status": "failed",
        "phase": phase,
        "error_message": sanitize_message_text(message),
        "completed_at": datetime.now(UTC),
    }
    if copied_points is not None:
        values["copied_points"] = copied_points
    if total_points is not None:
        values["total_points"] = total_points
    await _update_job(job_id, **values)
    await _insert_audit(job_id, "vector_migration.failed", {"error": values["error_message"]})


async def _update_job(job_id: uuid.UUID, **values: Any) -> None:
    async with session_factory()() as session:
        values["updated_at"] = sa.func.now()
        await session.execute(
            sa.update(VectorMigrationJob).where(VectorMigrationJob.id == job_id).values(**values)
        )
        await session.commit()


async def _insert_audit(job_id: uuid.UUID, action: str, metadata: dict[str, Any]) -> None:
    async with session_factory()() as session:
        job = await session.get(VectorMigrationJob, job_id)
        session.add(
            AuditLog(
                actor_id=job.created_by if job else None,
                actor_email=None,
                api_key_id=None,
                action=action,
                resource_type="vector_migration_job",
                resource_id=str(job_id),
                meta=metadata,
                ip=None,
                user_agent=None,
            )
        )
        await session.commit()
