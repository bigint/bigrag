from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import MaintenanceLock
from bigrag.services.maintenance import MAINTENANCE_LOCK_NAME

_BACKUP_LOCK_TTL_SECONDS = 1800
_BACKUP_LOCK_RENEW_SECONDS = 300


async def _set_lock_ttl(owner_id: uuid.UUID, ttl_seconds: int) -> None:
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    async with session_factory()() as session:
        await session.execute(
            sa.update(MaintenanceLock)
            .where(MaintenanceLock.name == MAINTENANCE_LOCK_NAME)
            .where(MaintenanceLock.owner_id == owner_id)
            .values(expires_at=expires_at)
        )
        await session.commit()


async def _renew_lock_until_cancelled(owner_id: uuid.UUID) -> None:
    while True:
        await asyncio.sleep(_BACKUP_LOCK_RENEW_SECONDS)
        await _set_lock_ttl(owner_id, _BACKUP_LOCK_TTL_SECONDS)
