from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from rag_computer.db.session import get_session
from rag_computer.main import create_app
from rag_computer.middleware.auth import get_current_user, require_admin_session, require_session


def now() -> datetime:
    return datetime(2026, 5, 9, tzinfo=UTC)


def user_principal(**overrides: Any) -> dict[str, Any]:
    value = {
        "id": str(uuid.uuid4()),
        "email": "admin@example.com",
        "display_name": "Admin",
        "role": "admin",
        "auth_method": "session",
        "api_key_id": None,
        "api_key_name": None,
        "scopes": None,
        "collection": None,
    }
    value.update(overrides)
    return value


@dataclass
class ScalarRows:
    rows: list[Any]

    def all(self) -> list[Any]:
        return self.rows


@dataclass
class ExecuteRows:
    rows: list[Any] = field(default_factory=list)

    def all(self) -> list[Any]:
        return self.rows

    def first(self) -> Any | None:
        return self.rows[0] if self.rows else None

    def one(self) -> Any:
        return self.rows[0]


@dataclass
class FakeSession:
    scalar_values: list[Any] = field(default_factory=list)
    scalars_values: list[list[Any]] = field(default_factory=list)
    execute_values: list[list[Any]] = field(default_factory=list)
    get_values: dict[Any, Any] = field(default_factory=dict)
    added: list[Any] = field(default_factory=list)
    deleted: list[Any] = field(default_factory=list)
    commits: int = 0
    refreshed: list[Any] = field(default_factory=list)

    async def scalar(self, _stmt: Any) -> Any:
        return self.scalar_values.pop(0) if self.scalar_values else None

    async def scalars(self, _stmt: Any) -> ScalarRows:
        return ScalarRows(self.scalars_values.pop(0) if self.scalars_values else [])

    async def execute(self, _stmt: Any) -> ExecuteRows:
        return ExecuteRows(self.execute_values.pop(0) if self.execute_values else [])

    async def get(self, _model: Any, key: Any) -> Any:
        return self.get_values.get(key) or self.get_values.get(str(key))

    def add(self, item: Any) -> None:
        self.added.append(item)

    async def delete(self, item: Any) -> None:
        self.deleted.append(item)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, item: Any) -> None:
        self.refreshed.append(item)


@pytest.fixture
def fake_session() -> FakeSession:
    return FakeSession()


@pytest.fixture(autouse=True)
def route_unit_middleware_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_active_lock() -> None:
        return None

    monkeypatch.setattr("rag_computer.middleware.maintenance.active_lock", no_active_lock)


@pytest.fixture
def route_client():
    clients: list[TestClient] = []

    def build(
        *,
        user: dict[str, Any] | None = None,
        session: FakeSession | None = None,
        unauthenticated: bool = False,
    ) -> TestClient:
        app = create_app()
        principal = user or user_principal()
        db = session or FakeSession()

        async def override_get_session() -> AsyncIterator[FakeSession]:
            yield db

        async def override_current_user() -> dict[str, Any]:
            if unauthenticated:
                raise HTTPException(status_code=401, detail="Authentication required")
            return principal

        async def override_session_user() -> dict[str, Any]:
            if principal.get("auth_method") != "session":
                raise HTTPException(status_code=403, detail="Session authentication required")
            return principal

        async def override_admin_user() -> dict[str, Any]:
            if principal.get("auth_method") != "session":
                raise HTTPException(status_code=403, detail="Session authentication required")
            if principal.get("role") != "admin":
                raise HTTPException(status_code=403, detail="Admin access required")
            return principal

        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_current_user] = override_current_user
        app.dependency_overrides[require_session] = override_session_user
        app.dependency_overrides[require_admin_session] = override_admin_user
        client = TestClient(app)
        clients.append(client)
        return client

    yield build

    for client in clients:
        client.close()


def row(**kwargs: Any) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def rows(values: Iterable[Any]) -> list[Any]:
    return list(values)
