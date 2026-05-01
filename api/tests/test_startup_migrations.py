from __future__ import annotations

import asyncio

from bigrag.config import Settings
from bigrag.main import _check_database_migrations


class FakeLogger:
    def info(self, *_args, **_kwargs) -> None:
        pass

    def error(self, *_args, **_kwargs) -> None:
        pass


def test_check_database_migrations_always_runs(monkeypatch) -> None:
    calls = 0

    async def fake_run_migrations() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr("bigrag.main.run_migrations", fake_run_migrations)

    settings = Settings(migration_timeout_seconds=0)
    asyncio.run(_check_database_migrations(settings, FakeLogger()))

    assert calls == 1
