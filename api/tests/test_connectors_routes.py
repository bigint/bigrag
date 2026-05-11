from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import FakeSession


class FakeRuntime:
    slug = "google"
    provider = "google"
    display_name = "Google Drive"
    error_query_param = "google_error"
    config_error = type("ConfigError", (Exception,), {})
    auth_error = type("AuthError", (Exception,), {})
    service_error = type("ServiceError", (Exception,), {})

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def get_config(self, _session):
        return {"client_id": "id"}

    async def get_account(self, _session, _user_id):
        return SimpleNamespace(id=uuid.uuid4(), provider=self.provider)

    def account_public(self, *, config, account):
        return {
            "provider": self.provider,
            "configured": True,
            "connected": True,
            "email": "u@x.com",
            "scopes": [],
            "expires_at": None,
            "connected_at": None,
        }

    async def list_files(self, _session, **_kwargs):
        return {
            "provider": self.provider,
            "parent_id": "root",
            "query": "",
            "files": [],
            "next_page_token": None,
        }

    async def list_sources(self, _session, **_kwargs):
        return ([], 0)

    async def build_oauth_url(self, _session, **_kwargs):
        return "https://oauth.example.com/authorize?state=abc"

    async def complete_oauth(self, _session, **_kwargs):
        return "/done"

    async def oauth_error_redirect_url(self, _session, **_kwargs):
        return "/settings?tab=connectors"

    async def disconnect_account(self, _session, **_kwargs):
        return None

    async def create_source(self, _session, **kwargs):
        source = SimpleNamespace(
            id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            collection_name=kwargs.get("collection_name"),
            root_id=kwargs.get("root_id"),
            source_type=kwargs.get("source_type"),
        )
        job = SimpleNamespace(id=uuid.uuid4())
        return source, job

    async def update_source(self, _session, **kwargs):
        return SimpleNamespace(
            id=uuid.UUID(kwargs["source_id"]),
            account_id=uuid.uuid4(),
        )

    async def delete_source(self, _session, **_kwargs):
        return None

    async def trigger_sync(self, _session, **_kwargs):
        return SimpleNamespace(id=uuid.uuid4())

    def source_public(self, _row):
        return {
            "id": str(uuid.uuid4()),
            "provider": self.provider,
            "collection_name": "docs",
            "root_id": "root-id",
            "root_name": "Folder",
            "root_mime_type": "folder",
            "source_type": "folder",
            "status": "idle",
            "schedule_enabled": True,
            "sync_interval_hours": 24,
            "last_sync_at": None,
            "next_sync_at": None,
            "last_error": None,
            "account_email": "u@x.com",
            "metadata": {},
            "created_at": "2026-05-09T00:00:00+00:00",
            "updated_at": "2026-05-09T00:00:00+00:00",
        }

    def sync_job_public(self, _job):
        return {
            "id": str(uuid.uuid4()),
            "provider": self.provider,
            "source_id": str(uuid.uuid4()),
            "trigger": "manual",
            "status": "pending",
            "total_found": 0,
            "total_created": 0,
            "total_updated": 0,
            "total_skipped": 0,
            "total_deleted": 0,
            "total_failed": 0,
            "error_message": None,
            "details": {},
            "started_at": None,
            "completed_at": None,
            "created_at": "2026-05-09T00:00:00+00:00",
            "updated_at": "2026-05-09T00:00:00+00:00",
        }


@pytest.fixture
def fake_runtime(monkeypatch: pytest.MonkeyPatch) -> FakeRuntime:
    runtime = FakeRuntime()
    from bigrag.routers import connectors

    monkeypatch.setattr(
        connectors, "connector_runtime", lambda slug: runtime if slug == "google" else None
    )
    monkeypatch.setattr(connectors.audit, "record", lambda *a, **k: None)

    async def fake_cors(_key):
        return ["http://testserver"]

    monkeypatch.setattr(connectors, "get_value", fake_cors)
    return runtime


def test_unknown_provider_returns_404(route_client) -> None:
    response = route_client().get("/v1/connectors/unknown/account")
    assert response.status_code == 404


def test_connector_account_happy_path(route_client, fake_runtime) -> None:
    response = route_client().get("/v1/connectors/google/account")

    assert response.status_code == 200
    assert response.json()["connected"] is True


def test_connector_files_config_error_returns_400(route_client, monkeypatch, fake_runtime) -> None:
    async def boom(_session, **_kwargs):
        raise fake_runtime.config_error("not configured")

    monkeypatch.setattr(fake_runtime, "list_files", boom)

    response = route_client().get("/v1/connectors/google/files")
    assert response.status_code == 400


def test_connector_files_auth_error_returns_401(route_client, monkeypatch, fake_runtime) -> None:
    async def boom(_session, **_kwargs):
        raise fake_runtime.auth_error("not signed in")

    monkeypatch.setattr(fake_runtime, "list_files", boom)

    response = route_client().get("/v1/connectors/google/files")
    assert response.status_code == 401


def test_connector_files_service_error_returns_502(route_client, monkeypatch, fake_runtime) -> None:
    async def boom(_session, **_kwargs):
        raise fake_runtime.service_error("api down")

    monkeypatch.setattr(fake_runtime, "list_files", boom)

    response = route_client().get("/v1/connectors/google/files")
    assert response.status_code == 502


def test_connector_files_happy_path(route_client, fake_runtime) -> None:
    response = route_client().get("/v1/connectors/google/files")
    assert response.status_code == 200
    assert response.json()["files"] == []


def test_connector_oauth_start_redirects(route_client, fake_runtime) -> None:
    response = route_client().get("/v1/connectors/google/oauth/start", follow_redirects=False)
    assert response.status_code in (302, 307)


def test_connector_oauth_start_url_returns_url(route_client, fake_runtime) -> None:
    response = route_client().get("/v1/connectors/google/oauth/start-url")
    assert response.status_code == 200
    assert response.json()["auth_url"].startswith("https://")


def test_connector_oauth_start_config_error_400(route_client, monkeypatch, fake_runtime) -> None:
    async def boom(_session, **_kwargs):
        raise fake_runtime.config_error("not configured")

    monkeypatch.setattr(fake_runtime, "build_oauth_url", boom)

    response = route_client().get("/v1/connectors/google/oauth/start-url")
    assert response.status_code == 400


def test_connector_oauth_callback_with_error_redirects(route_client, fake_runtime) -> None:
    response = route_client().get(
        "/v1/connectors/google/oauth/callback?error=access_denied",
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)


def test_connector_oauth_callback_missing_code_400(route_client, fake_runtime) -> None:
    response = route_client().get(
        "/v1/connectors/google/oauth/callback?state=abc",
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_connector_oauth_callback_happy_path(route_client, fake_runtime) -> None:
    response = route_client().get(
        "/v1/connectors/google/oauth/callback?code=c&state=s",
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)


def test_connector_oauth_callback_auth_error_redirects(
    route_client, monkeypatch, fake_runtime
) -> None:
    async def boom(_session, **_kwargs):
        raise fake_runtime.auth_error("bad token")

    monkeypatch.setattr(fake_runtime, "complete_oauth", boom)
    response = route_client().get(
        "/v1/connectors/google/oauth/callback?code=c&state=s",
        follow_redirects=False,
    )
    assert response.status_code in (302, 307)


def test_connector_disconnect(route_client, fake_runtime) -> None:
    response = route_client().post("/v1/connectors/google/disconnect")
    assert response.status_code == 200


def test_connector_sources_lists(route_client, fake_runtime) -> None:
    response = route_client().get("/v1/connectors/google/sources?collection=docs")
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_connector_source_create_happy_path(route_client, fake_runtime) -> None:
    session = FakeSession(get_values={uuid.uuid4(): SimpleNamespace(email="u@x.com")})
    response = route_client(session=session).post(
        "/v1/connectors/google/sources",
        json={
            "collection_name": "docs",
            "root_id": "root-id",
            "root_name": "Folder",
            "root_mime_type": "folder",
            "source_type": "folder",
        },
    )
    assert response.status_code == 201


def test_connector_source_create_value_error_404(route_client, monkeypatch, fake_runtime) -> None:
    async def boom(_session, **_kwargs):
        raise ValueError("source not found")

    monkeypatch.setattr(fake_runtime, "create_source", boom)
    response = route_client().post(
        "/v1/connectors/google/sources",
        json={
            "collection_name": "docs",
            "root_id": "root-id",
            "root_name": "Folder",
            "root_mime_type": "folder",
            "source_type": "folder",
        },
    )
    assert response.status_code == 404


def test_connector_source_update_happy_path(route_client, fake_runtime) -> None:
    source_id = str(uuid.uuid4())
    response = route_client().patch(
        f"/v1/connectors/google/sources/{source_id}",
        json={"schedule_enabled": False, "sync_interval_hours": 48},
    )
    assert response.status_code == 200


def test_connector_source_update_not_found(route_client, monkeypatch, fake_runtime) -> None:
    async def boom(_session, **_kwargs):
        raise ValueError("missing")

    monkeypatch.setattr(fake_runtime, "update_source", boom)
    response = route_client().patch(
        f"/v1/connectors/google/sources/{uuid.uuid4()}",
        json={"schedule_enabled": False},
    )
    assert response.status_code == 404


def test_connector_source_delete_happy_path(route_client, fake_runtime) -> None:
    response = route_client().delete(f"/v1/connectors/google/sources/{uuid.uuid4()}")
    assert response.status_code == 200


def test_connector_source_delete_not_found(route_client, monkeypatch, fake_runtime) -> None:
    async def boom(_session, **_kwargs):
        raise ValueError("missing")

    monkeypatch.setattr(fake_runtime, "delete_source", boom)
    response = route_client().delete(f"/v1/connectors/google/sources/{uuid.uuid4()}")
    assert response.status_code == 404


def test_connector_source_sync_happy_path(route_client, fake_runtime) -> None:
    response = route_client().post(f"/v1/connectors/google/sources/{uuid.uuid4()}/sync")
    assert response.status_code == 200


def test_connector_source_sync_value_error(route_client, monkeypatch, fake_runtime) -> None:
    async def boom(_session, **_kwargs):
        raise ValueError("source missing")

    monkeypatch.setattr(fake_runtime, "trigger_sync", boom)
    response = route_client().post(f"/v1/connectors/google/sources/{uuid.uuid4()}/sync")
    assert response.status_code == 404


def test_connector_sync_jobs_invalid_source_id_400(route_client, fake_runtime) -> None:
    response = route_client().get("/v1/connectors/google/sync-jobs?source_id=not-uuid")
    assert response.status_code == 400


def test_connector_sync_jobs_happy_path(route_client, monkeypatch, fake_runtime) -> None:
    from bigrag.routers import connectors

    async def fake_list(_session, **_kwargs):
        return ([], 0)

    monkeypatch.setattr(connectors, "list_connector_sync_jobs", fake_list)

    response = route_client().get(
        f"/v1/connectors/google/sync-jobs?source_id={uuid.uuid4()}&limit=5"
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0
