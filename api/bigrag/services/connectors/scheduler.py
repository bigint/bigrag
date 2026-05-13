from __future__ import annotations

import asyncio
from collections.abc import Callable

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import ConnectorSource
from bigrag.logging import get_logger
from bigrag.services.connectors.sources import create_sync_job
from bigrag.services.connectors.time import utcnow
from bigrag.utils import safe_create_task

logger = get_logger("bigrag.connectors")


async def run_due_syncs_logged(
    *,
    provider: str,
    start_sync_job: Callable[[str], None],
) -> None:
    try:
        await run_due_syncs(provider=provider, start_sync_job=start_sync_job)
    except Exception as exc:
        logger.warning(
            "connector: scheduler tick failed",
            provider=provider,
            error=str(exc),
        )


class ConnectorScheduler:
    def __init__(
        self,
        *,
        provider: str,
        start_sync_job: Callable[[str], None],
        interval_seconds: int = 60,
    ) -> None:
        self.provider = provider
        self.start_sync_job = start_sync_job
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = safe_create_task(self._loop(), name=f"{self.provider}_scheduler")
        logger.info(
            "connector: scheduler started",
            provider=self.provider,
            interval_seconds=self.interval_seconds,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("connector: scheduler stopped", provider=self.provider)

    async def _loop(self) -> None:
        while self._running:
            await run_due_syncs_logged(
                provider=self.provider,
                start_sync_job=self.start_sync_job,
            )
            await asyncio.sleep(self.interval_seconds)


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
            if job.status == "pending" and job.started_at is None:
                job_ids.append(str(job.id))
        await session.commit()
    for job_id in job_ids:
        start_sync_job(job_id)
    return len(job_ids)
