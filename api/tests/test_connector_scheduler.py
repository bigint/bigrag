from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

from bigrag.services import connector_core
from bigrag.services.connectors import scheduler


def test_run_due_syncs_logged_swallows_scheduler_tick_errors(monkeypatch) -> None:
    async def fail_run_due_syncs(**_kwargs):
        raise RuntimeError("scheduler failed")

    monkeypatch.setattr(connector_core, "run_due_syncs", fail_run_due_syncs)

    asyncio.run(
        connector_core.run_due_syncs_logged(
            provider="google_drive",
            start_sync_job=lambda _source_id: None,
        )
    )


class ScalarRows:
    def __init__(self, rows) -> None:
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows) -> None:
        self.rows = rows
        self.statements = []
        self.flushes = 0
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def scalars(self, stmt):
        self.statements.append(stmt)
        return ScalarRows(self.rows)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1


def test_run_due_syncs_claims_due_sources_with_skip_locked(monkeypatch) -> None:
    async def run() -> None:
        source = SimpleNamespace(id=uuid.uuid4())
        session = FakeSession([source])
        job_id = uuid.uuid4()
        started = []

        async def is_active():
            return False

        async def create_sync_job(session_arg, **kwargs):
            assert session_arg is session
            assert kwargs["source"] is source
            assert kwargs["trigger"] == "scheduled"
            return SimpleNamespace(id=job_id, status="pending", started_at=None)

        def session_factory():
            return lambda: session

        monkeypatch.setattr("bigrag.services.maintenance.is_active", is_active)
        monkeypatch.setattr(scheduler, "session_factory", session_factory)
        monkeypatch.setattr(scheduler, "create_sync_job", create_sync_job)

        count = await scheduler.run_due_syncs(
            provider="google",
            start_sync_job=started.append,
        )

        assert count == 1
        assert started == [str(job_id)]
        assert session.flushes == 1
        assert session.commits == 1
        assert session.statements[0]._for_update_arg.skip_locked is True

    asyncio.run(run())
