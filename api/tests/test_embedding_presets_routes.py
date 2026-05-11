from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from asyncpg.exceptions import UniqueViolationError
from conftest import FakeSession
from sqlalchemy.exc import IntegrityError


def _preset_row(**overrides):
    base = {
        "id": uuid.uuid4(),
        "name": "default",
        "provider": "openai",
        "model": "text-embedding-3-small",
        "base_url": None,
        "dimension": 1536,
        "api_key": "sk-fake",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class IntegritySession(FakeSession):
    def __init__(self, *args, fail_on_commit: bool = False, unique_error: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fail_on_commit = fail_on_commit
        self.unique_error = unique_error

    async def commit(self) -> None:
        if self.fail_on_commit:
            orig: Any = UniqueViolationError("dup") if self.unique_error else Exception("boom")
            raise IntegrityError("stmt", {}, orig)
        await super().commit()

    async def rollback(self) -> None:
        return None


def test_list_presets_returns_paginated(route_client) -> None:
    presets = [_preset_row(), _preset_row(name="other")]
    session = FakeSession(scalars_values=[presets], scalar_values=[2])

    response = route_client(session=session).get("/v1/admin/embedding-presets")

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_create_preset_rejects_bad_credentials(route_client, monkeypatch) -> None:
    from bigrag.routers import embedding_presets
    from bigrag.services.credential_check import CredentialCheckError

    async def bad_verify(**_kwargs):
        raise CredentialCheckError("invalid", "key invalid")

    monkeypatch.setattr(embedding_presets, "verify_provider_credentials", bad_verify)

    response = route_client().post(
        "/v1/admin/embedding-presets",
        json={
            "name": "test",
            "provider": "openai",
            "model": "text-embedding-3-small",
            "api_key": "sk",
            "dimension": 1536,
        },
    )

    assert response.status_code == 422


def test_create_preset_returns_409_on_unique_violation(route_client, monkeypatch) -> None:
    from bigrag.routers import embedding_presets

    async def ok_verify(**_kwargs):
        return None

    monkeypatch.setattr(embedding_presets, "verify_provider_credentials", ok_verify)
    monkeypatch.setattr(embedding_presets.audit, "record", lambda *a, **k: None)

    session = IntegritySession(fail_on_commit=True, unique_error=True)
    client = route_client(session=session)

    response = client.post(
        "/v1/admin/embedding-presets",
        json={
            "name": "dup",
            "provider": "openai",
            "model": "m",
            "api_key": "sk",
            "dimension": 1536,
        },
    )

    assert response.status_code == 409


def test_update_preset_invalid_uuid_returns_404(route_client) -> None:
    response = route_client().patch(
        "/v1/admin/embedding-presets/not-uuid",
        json={"name": "x"},
    )

    assert response.status_code == 404


def test_update_preset_not_found(route_client) -> None:
    response = route_client(session=FakeSession(get_values={})).patch(
        f"/v1/admin/embedding-presets/{uuid.uuid4()}",
        json={"name": "x"},
    )

    assert response.status_code == 404


def test_update_preset_happy_path(route_client, monkeypatch) -> None:
    from bigrag.routers import embedding_presets

    async def ok_verify(**_kwargs):
        return None

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(embedding_presets, "verify_provider_credentials", ok_verify)
    monkeypatch.setattr(embedding_presets.collection_cache, "invalidate_for_preset", noop)
    monkeypatch.setattr(embedding_presets, "invalidate_collection_query_cache", noop)
    monkeypatch.setattr(embedding_presets.audit, "record", lambda *a, **k: None)

    preset = _preset_row()
    session = FakeSession(
        get_values={preset.id: preset},
        scalars_values=[["docs"]],
    )
    response = route_client(session=session).patch(
        f"/v1/admin/embedding-presets/{preset.id}",
        json={"name": "renamed", "api_key": "sk-new"},
    )

    assert response.status_code == 200
    assert preset.name == "renamed"
    assert preset.api_key == "sk-new"


def test_delete_preset_invalid_uuid(route_client) -> None:
    response = route_client().delete("/v1/admin/embedding-presets/bad-uuid")

    assert response.status_code == 404


def test_delete_preset_not_found(route_client) -> None:
    response = route_client(session=FakeSession(get_values={})).delete(
        f"/v1/admin/embedding-presets/{uuid.uuid4()}"
    )

    assert response.status_code == 404


def test_delete_preset_409_when_referenced(route_client) -> None:
    preset = _preset_row()
    session = FakeSession(
        get_values={preset.id: preset},
        scalars_values=[["docs", "papers"]],
    )

    response = route_client(session=session).delete(f"/v1/admin/embedding-presets/{preset.id}")

    assert response.status_code == 409
    assert "in use by 2" in response.json()["detail"]


def test_delete_preset_happy_path(route_client, monkeypatch) -> None:
    from bigrag.routers import embedding_presets

    monkeypatch.setattr(embedding_presets.audit, "record", lambda *a, **k: None)

    preset = _preset_row()
    session = FakeSession(
        get_values={preset.id: preset},
        scalars_values=[[]],
    )

    response = route_client(session=session).delete(f"/v1/admin/embedding-presets/{preset.id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Preset deleted"
