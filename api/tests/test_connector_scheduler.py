from __future__ import annotations

import asyncio

from rag_computer.services import connector_core


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
