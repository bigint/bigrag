from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from bigrag.db.engine import session_factory
from bigrag.db.models import MaintenanceLock

BACKUP_LOCK_NAME = "backup"


class MaintenanceActiveError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


async def active_lock() -> MaintenanceLock | None:
    async with session_factory()() as session:
        return await session.scalar(
            sa.select(MaintenanceLock)
            .where(MaintenanceLock.expires_at > _now())
            .order_by(MaintenanceLock.created_at.asc())
            .limit(1)
        )


async def is_active() -> bool:
    return await active_lock() is not None


async def acquire_backup_lock(owner_id: uuid.UUID, *, ttl_hours: int = 12) -> bool:
    async with session_factory()() as session:
        await session.execute(
            sa.delete(MaintenanceLock).where(MaintenanceLock.expires_at <= _now())
        )
        session.add(
            MaintenanceLock(
                name=BACKUP_LOCK_NAME,
                owner_id=owner_id,
                reason="readable backup",
                expires_at=_now() + timedelta(hours=ttl_hours),
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return False
        return True


async def release_backup_lock(owner_id: uuid.UUID) -> None:
    async with session_factory()() as session:
        await session.execute(
            sa.delete(MaintenanceLock)
            .where(MaintenanceLock.name == BACKUP_LOCK_NAME)
            .where(MaintenanceLock.owner_id == owner_id)
        )
        await session.commit()


async def ensure_writes_allowed() -> None:
    lock = await active_lock()
    if lock is not None:
        raise MaintenanceActiveError(f"Instance maintenance active: {lock.reason}")
