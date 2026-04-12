"""E2E tests for bigRAG webhook admin endpoints.

Validates CRUD operations on /v1/admin/webhooks, delivery listing,
test delivery, auth enforcement, and input validation.
"""

from __future__ import annotations

import uuid

from unittest.mock import AsyncMock

from httpx import AsyncClient

from tests.conftest import install_fetchrow_router, make_delivery_row, make_webhook_row

WEBHOOK_URL = "https://example.com/hook"
WEBHOOK_EVENTS = ["document.ready"]


def _create_body(
    url: str = WEBHOOK_URL,
    events: list[str] | None = None,
    description: str = "test webhook",
) -> dict:
    return {
        "url": url,
        "events": events or WEBHOOK_EVENTS,
        "description": description,
    }




async def test_create_webhook(
    client: AsyncClient,
    auth_headers: dict,
    mock_db,
):
    wh_id = str(uuid.uuid4())
    row = make_webhook_row(webhook_id=wh_id)

    def fetchrow_router(query, *args):
        if "COUNT(*)" in query:
            return {"cnt": 0}
        if "INSERT INTO webhooks" in query:
            return row
        return None

    install_fetchrow_router(mock_db, fetchrow_router)

    resp = await client.post(
        "/v1/admin/webhooks",
        json=_create_body(),
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "secret" in body
    assert body["secret"] == "whsec_test123"
    assert body["url"] == "https://example.com/webhook"
    assert body["events"] == ["document.ready"]
    assert body["active"] is True


async def test_create_webhook_invalid_url(
    client: AsyncClient,
    auth_headers: dict,
):
    resp = await client.post(
        "/v1/admin/webhooks",
        json=_create_body(url="http://not-localhost.example.com/hook"),
        headers=auth_headers,
    )
    assert resp.status_code == 422


async def test_create_webhook_invalid_events(
    client: AsyncClient,
    auth_headers: dict,
):
    resp = await client.post(
        "/v1/admin/webhooks",
        json=_create_body(events=["invalid.event"]),
        headers=auth_headers,
    )
    assert resp.status_code == 422




async def test_list_webhooks(
    client: AsyncClient,
    auth_headers: dict,
    mock_db,
):
    rows = [make_webhook_row(), make_webhook_row()]
    mock_db.fetch.return_value = rows

    resp = await client.get("/v1/admin/webhooks", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "webhooks" in body
    assert len(body["webhooks"]) == 2




async def test_get_webhook(
    client: AsyncClient,
    auth_headers: dict,
    mock_db,
):
    wh_id = str(uuid.uuid4())
    row = make_webhook_row(webhook_id=wh_id)
    mock_db.fetchrow.return_value = row

    resp = await client.get(f"/v1/admin/webhooks/{wh_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == wh_id
    assert "secret" not in body


async def test_get_webhook_not_found(
    client: AsyncClient,
    auth_headers: dict,
    mock_db,
):
    mock_db.fetchrow.return_value = None

    wh_id = str(uuid.uuid4())
    resp = await client.get(f"/v1/admin/webhooks/{wh_id}", headers=auth_headers)
    assert resp.status_code == 404




async def test_update_webhook(
    client: AsyncClient,
    auth_headers: dict,
    mock_db,
):
    wh_id = str(uuid.uuid4())
    row = make_webhook_row(webhook_id=wh_id)
    updated_row = make_webhook_row(webhook_id=wh_id, description="updated")

    call_count = 0

    def fetchrow_router(query, *args):
        nonlocal call_count
        call_count += 1
        if "webhooks WHERE id" in query:
            return row
        if "UPDATE" in query:
            return updated_row
        return None

    install_fetchrow_router(mock_db, fetchrow_router)

    resp = await client.put(
        f"/v1/admin/webhooks/{wh_id}",
        json={"description": "updated"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["description"] == "updated"




async def test_delete_webhook(
    client: AsyncClient,
    auth_headers: dict,
    mock_db,
):
    wh_id = str(uuid.uuid4())
    row = make_webhook_row(webhook_id=wh_id)

    def fetchrow_router(query, *args):
        if "webhooks WHERE id" in query:
            return row
        return None

    install_fetchrow_router(mock_db, fetchrow_router)

    resp = await client.delete(f"/v1/admin/webhooks/{wh_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"




async def test_list_deliveries(
    client: AsyncClient,
    auth_headers: dict,
    mock_db,
):
    wh_id = str(uuid.uuid4())
    wh_row = make_webhook_row(webhook_id=wh_id)
    delivery = make_delivery_row(webhook_id=wh_id)

    def fetchrow_router(query, *args):
        if "webhooks WHERE id" in query:
            return wh_row
        if "COUNT(*)" in query:
            return {"cnt": 1}
        return None

    install_fetchrow_router(mock_db, fetchrow_router)
    mock_db.fetch.return_value = [delivery]

    resp = await client.get(
        f"/v1/admin/webhooks/{wh_id}/deliveries",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "deliveries" in body
    assert body["total"] == 1
    assert len(body["deliveries"]) == 1




async def test_test_webhook(
    client: AsyncClient,
    auth_headers: dict,
    mock_db,
    mock_webhook_dispatcher,
):
    wh_id = str(uuid.uuid4())
    row = make_webhook_row(webhook_id=wh_id)
    mock_db.fetchrow.return_value = row

    resp = await client.post(
        f"/v1/admin/webhooks/{wh_id}/test",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "delivered"
    assert body["status_code"] == 200
    assert body["error"] is None
    mock_webhook_dispatcher.deliver_test.assert_awaited_once()




async def test_replay_delivery_fires_deliver_once(
    client: AsyncClient, auth_headers: dict, mock_db, mock_webhook_dispatcher
):
    """POST /webhooks/:id/deliveries/:delivery_id/replay should re-fire
    using the stored payload and event, via deliver_once (not the full
    retry pipeline)."""
    wh_id = str(uuid.uuid4())
    del_id = str(uuid.uuid4())
    webhook = make_webhook_row(webhook_id=wh_id)
    delivery = make_delivery_row(
        delivery_id=del_id,
        webhook_id=wh_id,
        event="document.ready",
        payload={"event": "document.ready", "document_id": "doc-1"},
    )

    def router(query, *args):
        if "FROM webhooks WHERE id" in query:
            return webhook
        if "FROM webhook_deliveries WHERE id" in query:
            return delivery
        return None

    install_fetchrow_router(mock_db, router)
    mock_webhook_dispatcher.deliver_once = AsyncMock(
        return_value={"status": "delivered", "status_code": 200, "error": None},
    )

    resp = await client.post(
        f"/v1/admin/webhooks/{wh_id}/deliveries/{del_id}/replay",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "delivered"
    mock_webhook_dispatcher.deliver_once.assert_awaited_once()
    # Confirm the same event+payload were re-used.
    call_args = mock_webhook_dispatcher.deliver_once.await_args
    assert call_args.args[1] == "document.ready"
    assert '"document_id":"doc-1"' in call_args.args[2]


async def test_webhooks_require_auth(client: AsyncClient):
    # The client fixture pre-attaches a valid session cookie so most
    # tests don't have to. This one needs the opposite — verify the
    # endpoints reject unauthenticated requests.
    client.cookies.clear()
    endpoints = [
        ("POST", "/v1/admin/webhooks"),
        ("GET", "/v1/admin/webhooks"),
        ("GET", f"/v1/admin/webhooks/{uuid.uuid4()}"),
        ("PUT", f"/v1/admin/webhooks/{uuid.uuid4()}"),
        ("DELETE", f"/v1/admin/webhooks/{uuid.uuid4()}"),
        ("GET", f"/v1/admin/webhooks/{uuid.uuid4()}/deliveries"),
        ("POST", f"/v1/admin/webhooks/{uuid.uuid4()}/test"),
    ]
    for method, path in endpoints:
        resp = await client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} should require auth"
