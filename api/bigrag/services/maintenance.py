from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import MaintenanceLock

_LOCK_STATE_CACHE_KEY = "maintenance:lock_state"
_LOCK_STATE_CACHE_TTL = 5


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


async def active_lock_state() -> dict | None:
    from bigrag.services import redis_cache

    cached = await redis_cache.get(_LOCK_STATE_CACHE_KEY)
    if cached is not None:
        return cached.get("lock")
    lock = await active_lock()
    state = {"reason": lock.reason} if lock is not None else None
    await redis_cache.set(_LOCK_STATE_CACHE_KEY, {"lock": state}, _LOCK_STATE_CACHE_TTL)
    return state


async def ensure_writes_allowed() -> None:
    lock = await active_lock_state()
    if lock is not None:
        raise MaintenanceActiveError(f"Instance maintenance active: {lock['reason']}")
