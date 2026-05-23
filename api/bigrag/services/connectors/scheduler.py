from __future__ import annotations

from collections.abc import Callable

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import ConnectorSource
from bigrag.services.connectors.realtime import notify_connector_state
from bigrag.services.connectors.sources import create_sync_job
from bigrag.services.connectors.time import utcnow


async def run_due_syncs(
    *,
    provider: str,
    start_sync_job: Callable[[str], None],
    limit: int = 10,
) -> int:
    from bigrag.services.maintenance import is_active

    if await is_active():
        return 0
    job_ids: list[str] = []
    notifications: list[tuple[str, str, str]] = []
    async with session_factory()() as session:
        rows = (
            await session.scalars(
                sa.select(ConnectorSource)
                .where(ConnectorSource.provider == provider)
                .where(ConnectorSource.schedule_enabled.is_(True))
                .where(ConnectorSource.next_sync_at.is_not(None))
                .where(ConnectorSource.next_sync_at <= utcnow())
                .where(ConnectorSource.status != "syncing")
                .order_by(ConnectorSource.next_sync_at.asc())
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        ).all()
        for source in rows:
            job = await create_sync_job(
                session,
                provider=provider,
                source=source,
                trigger="scheduled",
                user_id=None,
                commit=False,
            )
            await session.flush()
            notifications.append((provider, source.collection_name, str(source.id)))
            if job.status == "pending" and job.started_at is None:
                job_ids.append(str(job.id))
        await session.commit()
    for event in notifications:
        notify_connector_state(*event)
    for job_id in job_ids:
        start_sync_job(job_id)
    return len(job_ids)
