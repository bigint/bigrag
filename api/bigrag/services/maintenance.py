from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

from bigrag.db.engine import session_factory
from bigrag.db.models import MaintenanceLock

MAINTENANCE_LOCK_NAME = "maintenance"
BACKUP_LOCK_NAME = MAINTENANCE_LOCK_NAME


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


async def acquire_maintenance_lock(
    owner_id: uuid.UUID,
    *,
    reason: str,
    ttl_hours: int = 12,
    metadata: dict | None = None,
) -> bool:
    now = _now()
    expires_at = now + timedelta(hours=ttl_hours)
    stmt = pg_insert(MaintenanceLock).values(
        name=MAINTENANCE_LOCK_NAME,
        owner_id=owner_id,
        reason=reason,
        expires_at=expires_at,
        meta=metadata or {},
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[MaintenanceLock.name],
        set_={
            "owner_id": stmt.excluded.owner_id,
            "reason": stmt.excluded.reason,
            "expires_at": stmt.excluded.expires_at,
            "meta": stmt.excluded.meta,
        },
        where=MaintenanceLock.expires_at <= now,
    ).returning(MaintenanceLock.owner_id)
    async with session_factory()() as session:
        other = await session.scalar(
            sa.select(MaintenanceLock)
            .where(MaintenanceLock.name != MAINTENANCE_LOCK_NAME)
            .where(MaintenanceLock.expires_at > now)
            .limit(1)
        )
        if other is not None:
            return False
        result = await session.execute(stmt)
        row = result.first()
        await session.commit()
        return row is not None and row[0] == owner_id


async def release_maintenance_lock(owner_id: uuid.UUID) -> None:
    async with session_factory()() as session:
        await session.execute(
            sa.delete(MaintenanceLock)
            .where(MaintenanceLock.name == MAINTENANCE_LOCK_NAME)
            .where(MaintenanceLock.owner_id == owner_id)
        )
        await session.commit()


async def acquire_backup_lock(owner_id: uuid.UUID, *, ttl_hours: int = 12) -> bool:
    return await acquire_maintenance_lock(
        owner_id,
        reason="readable backup",
        ttl_hours=ttl_hours,
    )


async def release_backup_lock(owner_id: uuid.UUID) -> None:
    await release_maintenance_lock(owner_id)


async def ensure_writes_allowed() -> None:
    lock = await active_lock()
    if lock is not None:
        raise MaintenanceActiveError(f"Instance maintenance active: {lock.reason}")
