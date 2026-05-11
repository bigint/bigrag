from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from bigrag.services import maintenance


def run(coro):
    return asyncio.run(coro)


class FakeSession:
    def __init__(self, *, active=None, fail_commit=False) -> None:
        self.active = active
        self.fail_commit = fail_commit
        self.executed = 0
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def scalar(self, _stmt):
        return self.active

    async def execute(self, _stmt):
        self.executed += 1

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commits += 1
        if self.fail_commit:
            raise IntegrityError("insert", {}, Exception("duplicate"))

    async def rollback(self):
        self.rollbacks += 1


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return False


def patch_session(monkeypatch, session: FakeSession) -> None:
    monkeypatch.setattr(
        maintenance,
        "session_factory",
        lambda: lambda: FakeSessionContext(session),
    )


def test_active_lock_and_write_guard(monkeypatch) -> None:
    lock = SimpleNamespace(reason="readable backup")
    patch_session(monkeypatch, FakeSession(active=lock))

    assert run(maintenance.active_lock()) is lock
    assert run(maintenance.is_active()) is True

    with pytest.raises(maintenance.MaintenanceActiveError, match="readable backup"):
        run(maintenance.ensure_writes_allowed())

    patch_session(monkeypatch, FakeSession(active=None))

    assert run(maintenance.is_active()) is False
    run(maintenance.ensure_writes_allowed())


def test_acquire_backup_lock_success_and_conflict(monkeypatch) -> None:
    owner_id = uuid.uuid4()
    session = FakeSession()
    patch_session(monkeypatch, session)

    assert run(maintenance.acquire_backup_lock(owner_id, ttl_hours=1)) is True
    assert session.executed == 1
    assert session.commits == 1
    assert session.added[0].name == maintenance.BACKUP_LOCK_NAME
    assert session.added[0].owner_id == owner_id

    conflict = FakeSession(fail_commit=True)
    patch_session(monkeypatch, conflict)

    assert run(maintenance.acquire_backup_lock(owner_id)) is False
    assert conflict.rollbacks == 1


def test_release_backup_lock_deletes_owner_lock(monkeypatch) -> None:
    session = FakeSession()
    patch_session(monkeypatch, session)

    run(maintenance.release_backup_lock(uuid.uuid4()))

    assert session.executed == 1
    assert session.commits == 1
