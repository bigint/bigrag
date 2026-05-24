from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import AuditLog, BackupJob
from bigrag.services.error_sanitize import sanitize_message_text
from bigrag.services.webhook import enqueue_webhook_event


async def _mark_job_running(job_id: uuid.UUID) -> None:
    await _update_job(job_id, status="running", progress=0.03, started_at=datetime.now(UTC))
    await _insert_audit(job_id, "backup.start", {})
    await _enqueue_backup_event(job_id, "backup.started")


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
    await _enqueue_backup_event(job_id, "backup.succeeded")


async def _fail_job(job_id: uuid.UUID, message: str) -> None:
    await _update_job(
        job_id,
        status="failed",
        error_message=message,
        completed_at=datetime.now(UTC),
    )
    await _insert_audit(job_id, "backup.failed", {"error": message})
    await _enqueue_backup_event(job_id, "backup.failed")


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


async def _enqueue_backup_event(job_id: uuid.UUID, event: str) -> None:
    data = await _backup_event_data(job_id)
    await enqueue_webhook_event(event, data=data)


async def _backup_event_data(job_id: uuid.UUID) -> dict[str, Any]:
    async with session_factory()() as session:
        job = await session.get(BackupJob, job_id)
    if job is None:
        return {"job_id": str(job_id)}
    error_message = sanitize_message_text(job.error_message or "") if job.error_message else None
    return {
        "job_id": str(job.id),
        "label": job.label,
        "status": job.status,
        "progress": job.progress,
        "destination_prefix": job.destination_prefix,
        "object_count": job.object_count,
        "byte_count": job.byte_count,
        "error_message": error_message,
    }
