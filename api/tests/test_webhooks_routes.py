from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from conftest import FakeSession


def _webhook_row(**overrides):
    base = {
        "id": uuid.uuid4(),
        "url": "https://example.com/hook",
        "secret": "secret",
        "events": ["document.ready"],
        "collections": None,
        "description": "",
        "active": True,
        "created_by": uuid.uuid4(),
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _delivery_row(**overrides):
    base = {
        "id": uuid.uuid4(),
        "webhook_id": uuid.uuid4(),
        "event": "document.ready",
        "payload": {"a": 1},
        "status": "delivered",
        "attempts": 1,
        "last_status_code": 200,
        "last_error": None,
        "next_retry_at": None,
        "created_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def patch_webhooks(monkeypatch: pytest.MonkeyPatch):
    from bigrag.routers import webhooks

    async def fake_resolve(_url):
        return None

    async def fake_max(_key):
        return 50

    monkeypatch.setattr(webhooks, "resolve_and_validate_url", fake_resolve)
    monkeypatch.setattr(webhooks, "get_value", fake_max)
    monkeypatch.setattr(webhooks, "generate_secret", lambda: "the-secret")
    monkeypatch.setattr(webhooks.audit, "record", lambda *a, **k: None)


def test_create_webhook_rejects_when_at_limit(route_client, patch_webhooks, monkeypatch) -> None:
    from bigrag.routers import webhooks

    async def low_max(_key):
        return 1

    monkeypatch.setattr(webhooks, "get_value", low_max)

    session = FakeSession(scalar_values=[5])

    response = route_client(session=session).post(
        "/v1/admin/webhooks",
        json={"url": "https://x.example.com/h", "events": ["document.ready"]},
    )

    assert response.status_code == 400
    assert "Maximum" in response.json()["detail"]


def test_create_webhook_rejects_invalid_url(route_client, monkeypatch, patch_webhooks) -> None:
    from bigrag.routers import webhooks

    async def fail_validate(_url):
        raise ValueError("not allowed")

    monkeypatch.setattr(webhooks, "resolve_and_validate_url", fail_validate)

    session = FakeSession(scalar_values=[0])

    response = route_client(session=session).post(
        "/v1/admin/webhooks",
        json={"url": "https://x.example.com/h", "events": ["document.ready"]},
    )

    assert response.status_code == 400


def test_create_webhook_happy_path(route_client, patch_webhooks) -> None:
    class _RefreshSession(FakeSession):
        async def refresh(self, item):
            now = datetime.now(UTC)
            if not getattr(item, "created_at", None):
                item.created_at = now
            if not getattr(item, "updated_at", None):
                item.updated_at = now
            if getattr(item, "active", None) is None:
                item.active = True
            self.refreshed.append(item)

    session = _RefreshSession(scalar_values=[0])

    response = route_client(session=session).post(
        "/v1/admin/webhooks",
        json={
            "url": "https://x.example.com/h",
            "events": ["document.ready"],
            "collections": ["docs"],
        },
    )

    assert response.status_code == 201
    assert response.json()["secret"] == "the-secret"


def test_list_webhooks_returns_collection(route_client) -> None:
    webhooks_list = [_webhook_row(), _webhook_row(active=False)]
    session = FakeSession(scalars_values=[webhooks_list])

    response = route_client(session=session).get("/v1/admin/webhooks")

    assert response.status_code == 200
    assert len(response.json()["webhooks"]) == 2


def test_get_webhook_bad_uuid(route_client) -> None:
    response = route_client().get("/v1/admin/webhooks/not-uuid")

    assert response.status_code == 404


def test_get_webhook_not_found(route_client) -> None:
    response = route_client(session=FakeSession(get_values={})).get(
        f"/v1/admin/webhooks/{uuid.uuid4()}"
    )

    assert response.status_code == 404


def test_get_webhook_happy_path(route_client) -> None:
    wh = _webhook_row()
    session = FakeSession(get_values={wh.id: wh})

    response = route_client(session=session).get(f"/v1/admin/webhooks/{wh.id}")

    assert response.status_code == 200
    assert response.json()["url"] == wh.url


def test_update_webhook_not_found(route_client) -> None:
    response = route_client(session=FakeSession(get_values={})).put(
        f"/v1/admin/webhooks/{uuid.uuid4()}",
        json={"description": "new"},
    )

    assert response.status_code == 404


def test_update_webhook_full_fields(route_client, patch_webhooks) -> None:
    wh = _webhook_row()
    session = FakeSession(get_values={wh.id: wh})

    response = route_client(session=session).put(
        f"/v1/admin/webhooks/{wh.id}",
        json={
            "url": "https://new.example.com/h",
            "events": ["document.failed"],
            "collections": ["docs"],
            "description": "new",
            "active": False,
        },
    )

    assert response.status_code == 200
    assert wh.url == "https://new.example.com/h"
    assert wh.active is False


def test_delete_webhook_not_found(route_client) -> None:
    response = route_client(session=FakeSession(get_values={})).delete(
        f"/v1/admin/webhooks/{uuid.uuid4()}"
    )

    assert response.status_code == 404


def test_delete_webhook_happy_path(route_client, patch_webhooks) -> None:
    wh = _webhook_row()
    session = FakeSession(get_values={wh.id: wh})

    response = route_client(session=session).delete(f"/v1/admin/webhooks/{wh.id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Webhook deleted"


def test_list_deliveries_webhook_not_found(route_client) -> None:
    session = FakeSession(scalar_values=[None])

    response = route_client(session=session).get(f"/v1/admin/webhooks/{uuid.uuid4()}/deliveries")

    assert response.status_code == 404


def test_list_deliveries_happy_path(route_client) -> None:
    wh_id = uuid.uuid4()
    deliveries = [_delivery_row(webhook_id=wh_id), _delivery_row(webhook_id=wh_id)]
    session = FakeSession(
        scalar_values=[wh_id, 2],
        scalars_values=[deliveries],
    )

    response = route_client(session=session).get(f"/v1/admin/webhooks/{wh_id}/deliveries?limit=5")

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_test_webhook_not_found(route_client) -> None:
    response = route_client(session=FakeSession(get_values={})).post(
        f"/v1/admin/webhooks/{uuid.uuid4()}/test"
    )

    assert response.status_code == 404


def test_test_webhook_happy_path(route_client, monkeypatch, patch_webhooks) -> None:
    from bigrag.routers import webhooks

    async def fake_test(_wh):
        return {
            "status": "delivered",
            "status_code": 200,
            "duration_ms": 5,
            "error": None,
        }

    monkeypatch.setattr(webhooks.webhook_dispatcher, "deliver_test", fake_test)

    wh = _webhook_row()
    session = FakeSession(get_values={wh.id: wh})

    response = route_client(session=session).post(f"/v1/admin/webhooks/{wh.id}/test")

    assert response.status_code == 200
    assert response.json()["status"] == "delivered"


def test_replay_delivery_delivery_not_found(route_client, monkeypatch, patch_webhooks) -> None:
    wh = _webhook_row()
    session = FakeSession(get_values={wh.id: wh}, scalar_values=[None])

    response = route_client(session=session).post(
        f"/v1/admin/webhooks/{wh.id}/deliveries/{uuid.uuid4()}/replay"
    )

    assert response.status_code == 404


def test_replay_delivery_happy_path(route_client, monkeypatch, patch_webhooks) -> None:
    from bigrag.routers import webhooks

    async def fake_once(_wh, _event, _payload):
        return {
            "status": "delivered",
            "status_code": 200,
            "duration_ms": 3,
            "error": None,
        }

    monkeypatch.setattr(webhooks.webhook_dispatcher, "deliver_once", fake_once)

    wh = _webhook_row()
    delivery = _delivery_row(webhook_id=wh.id)
    session = FakeSession(get_values={wh.id: wh}, scalar_values=[delivery])

    response = route_client(session=session).post(
        f"/v1/admin/webhooks/{wh.id}/deliveries/{delivery.id}/replay"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "delivered"
