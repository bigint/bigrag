from __future__ import annotations

import asyncio

from bigrag.services import cleanup


class FakeDeleteResult:
    def __init__(self, rowcount: int | None) -> None:
        self.rowcount = rowcount


class FakeSession:
    def __init__(self) -> None:
        self.results = [
            FakeDeleteResult(1),
            FakeDeleteResult(2),
            FakeDeleteResult(None),
            FakeDeleteResult(4),
        ]
        self.executed = 0
        self.commits = 0

    async def execute(self, _stmt):
        self.executed += 1
        return self.results.pop(0)

    async def commit(self) -> None:
        self.commits += 1


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, *_args) -> bool:
        return False


class FakeLogger:
    def __init__(self) -> None:
        self.infos = []
        self.warnings = []

    def info(self, message: str, **kwargs) -> None:
        self.infos.append((message, kwargs))

    def warning(self, message: str, **kwargs) -> None:
        self.warnings.append((message, kwargs))


def run(coro):
    return asyncio.run(coro)


def test_cleanup_old_data_runs_retention_deletes_and_embedding_purge(monkeypatch) -> None:
    session = FakeSession()
    logger = FakeLogger()
    sleep_calls = 0
    purged_days = []

    async def sleep(_seconds: int) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise asyncio.CancelledError

    async def get_values(_keys):
        return {
            "query_log_retention_days": 7,
            "access_log_retention_days": 14,
            "webhook_delivery_retention_days": 21,
            "upload_session_item_retention_hours": 48,
            "embedding_cache_retention_days": 30,
        }

    async def purge_stale(days: int) -> int:
        purged_days.append(days)
        return 5

    monkeypatch.setattr(cleanup.asyncio, "sleep", sleep)
    monkeypatch.setattr(cleanup, "get_values", get_values)
    monkeypatch.setattr(cleanup, "session_factory", lambda: lambda: FakeSessionContext(session))
    monkeypatch.setattr(cleanup.embedding_cache, "purge_stale", purge_stale)
    monkeypatch.setattr(cleanup, "logger", logger)

    run(cleanup.cleanup_old_data())

    assert session.executed == 4
    assert session.commits == 1
    assert purged_days == [30]
    assert logger.infos == [
        ("query_log cleanup", {"deleted": 1}),
        ("access_log cleanup", {"deleted": 2}),
        ("webhook_deliveries cleanup", {"deleted": 0}),
        ("upload_sessions cleanup", {"deleted": 4}),
        ("embedding_cache cleanup", {"deleted": 5}),
    ]


def test_cleanup_old_data_logs_failure_and_continues_until_cancelled(monkeypatch) -> None:
    logger = FakeLogger()
    sleep_calls = 0

    async def sleep(_seconds: int) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise asyncio.CancelledError

    async def fail_values(_keys):
        raise RuntimeError("settings unavailable")

    monkeypatch.setattr(cleanup.asyncio, "sleep", sleep)
    monkeypatch.setattr(cleanup, "get_values", fail_values)
    monkeypatch.setattr(cleanup, "logger", logger)

    run(cleanup.cleanup_old_data())

    assert logger.warnings == [
        ("cleanup failed", {"error": "RuntimeError('settings unavailable')"})
    ]
