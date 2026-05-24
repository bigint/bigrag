from __future__ import annotations

import uuid

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import BackupJob
from bigrag.services.backup.target import BackupConfigError
from bigrag.services.maintenance import active_lock


async def create_backup_job(*, label: str, created_by: uuid.UUID | None) -> BackupJob:
    lock = await active_lock()
    if lock is not None:
        raise BackupConfigError(f"Instance maintenance active: {lock.reason}")
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
