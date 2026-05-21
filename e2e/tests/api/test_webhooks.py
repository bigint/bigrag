"""End-to-end tests for bigrag.routers.webhooks.

Endpoints covered:
- POST   /v1/admin/webhooks
- GET    /v1/admin/webhooks
- GET    /v1/admin/webhooks/{webhook_id}
- PUT    /v1/admin/webhooks/{webhook_id}
- DELETE /v1/admin/webhooks/{webhook_id}
- GET    /v1/admin/webhooks/{webhook_id}/deliveries
- POST   /v1/admin/webhooks/{webhook_id}/test
- POST   /v1/admin/webhooks/{webhook_id}/deliveries/{delivery_id}/replay
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import httpx
import orjson
import pytest

from tests._helpers import assert_envelope, poll_until, unique_name


def _verify_signature(secret: str, body: bytes, header: str, timestamp: str | None) -> bool:
    signed = f"{timestamp}.{body.decode()}" if timestamp else body.decode()
    digest = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={digest}", header)


async def _create_webhook(
    admin_client: httpx.AsyncClient,
    url: str,
    *,
    events: list[str] | None = None,
    collections: list[str] | None = None,
    description: str = "",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "url": url,
        "events": events or ["document.ready", "document.failed"],
        "description": description,
    }
    if collections is not None:
        body["collections"] = collections
    resp = await admin_client.post("/v1/admin/webhooks", json=body)
    return assert_envelope(resp, 201)


async def _cleanup_webhook(admin_client: httpx.AsyncClient, webhook_id: str) -> None:
    try:
        await admin_client.delete(f"/v1/admin/webhooks/{webhook_id}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def test_create_webhook_returns_secret_and_persists(
    admin_client: httpx.AsyncClient,
    webhook_sink: dict[str, Any],
) -> None:
    label = unique_name("hook")
    created = await _create_webhook(
        admin_client,
        webhook_sink["url"](label),
        events=["document.ready"],
        description="created in e2e",
    )
    try:
        assert created["secret"].startswith("whsec_")
        assert created["events"] == ["document.ready"]
        assert created["active"] is True
        assert created["url"].endswith(label)

        resp = await admin_client.get(f"/v1/admin/webhooks/{created['id']}")
        fetched = assert_envelope(resp, 200)
        assert fetched["id"] == created["id"]
        assert "secret" not in fetched
    finally:
        await _cleanup_webhook(admin_client, created["id"])


async def test_list_webhooks_includes_created_and_paginates(
    admin_client: httpx.AsyncClient,
    webhook_sink: dict[str, Any],
) -> None:
    created_ids: list[str] = []
    try:
        for _ in range(3):
            label = unique_name("hook")
            wh = await _create_webhook(admin_client, webhook_sink["url"](label))
            created_ids.append(wh["id"])

        resp = await admin_client.get(
            "/v1/admin/webhooks", params={"limit": 100, "include_total": "true"}
        )
        body = assert_envelope(resp, 200)
        ids = {w["id"] for w in body["webhooks"]}
        for cid in created_ids:
            assert cid in ids
        assert body["total"] >= 3

        resp_paginated = await admin_client.get(
            "/v1/admin/webhooks", params={"limit": 1, "offset": 0}
        )
        body_paginated = assert_envelope(resp_paginated, 200)
        assert len(body_paginated["webhooks"]) == 1
    finally:
        for cid in created_ids:
            await _cleanup_webhook(admin_client, cid)


async def test_get_webhook_404_for_unknown(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.get("/v1/admin/webhooks/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404, resp.text

    resp = await admin_client.get("/v1/admin/webhooks/not-a-uuid")
    assert resp.status_code == 404, resp.text


async def test_update_webhook_changes_events_and_active(
    admin_client: httpx.AsyncClient,
    webhook_sink: dict[str, Any],
) -> None:
    label = unique_name("hook")
    created = await _create_webhook(
        admin_client,
        webhook_sink["url"](label),
        events=["document.ready"],
    )
    try:
        resp = await admin_client.put(
            f"/v1/admin/webhooks/{created['id']}",
            json={
                "events": ["document.failed"],
                "description": "updated",
                "active": False,
            },
        )
        updated = assert_envelope(resp, 200)
        assert updated["events"] == ["document.failed"]
        assert updated["description"] == "updated"
        assert updated["active"] is False
    finally:
        await _cleanup_webhook(admin_client, created["id"])


async def test_delete_webhook_removes_it(
    admin_client: httpx.AsyncClient,
    webhook_sink: dict[str, Any],
) -> None:
    label = unique_name("hook")
    created = await _create_webhook(admin_client, webhook_sink["url"](label))
    resp = await admin_client.delete(f"/v1/admin/webhooks/{created['id']}")
    assert_envelope(resp, 200)

    resp = await admin_client.get(f"/v1/admin/webhooks/{created['id']}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test delivery / signature / replay
# ---------------------------------------------------------------------------


async def test_test_delivery_reaches_sink_with_valid_signature(
    admin_client: httpx.AsyncClient,
    webhook_sink: dict[str, Any],
) -> None:
    label = unique_name("hook")
    created = await _create_webhook(admin_client, webhook_sink["url"](label))
    try:
        resp = await admin_client.post(f"/v1/admin/webhooks/{created['id']}/test")
        body = assert_envelope(resp, 200)
        assert body["status"] == "delivered"
        assert body["status_code"] == 200

        deliveries = await webhook_sink["wait"](label, count=1)
        assert len(deliveries) >= 1
        first = deliveries[0]
        headers = {k.lower(): v for k, v in first["headers"].items()}
        signature = headers.get("x-bigrag-signature")
        timestamp = headers.get("x-bigrag-timestamp")
        assert signature and signature.startswith("sha256=")
        body_bytes = orjson.dumps(first["body"])
        assert _verify_signature(created["secret"], body_bytes, signature, timestamp)
        assert headers.get("x-bigrag-event") == "webhook.test"
    finally:
        await _cleanup_webhook(admin_client, created["id"])


async def test_test_delivery_404_for_missing_webhook(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post("/v1/admin/webhooks/00000000-0000-0000-0000-000000000000/test")
    assert resp.status_code == 404


async def test_document_ready_dispatches_webhook(
    admin_client: httpx.AsyncClient,
    collection,
    document,
    webhook_sink: dict[str, Any],
) -> None:
    coll = await collection()
    label = unique_name("hook")
    created = await _create_webhook(
        admin_client,
        webhook_sink["url"](label),
        events=["document.ready", "document.failed"],
        collections=[coll["name"]],
    )
    try:
        doc = await document(coll["name"], fixture="sample.txt")
        assert doc["status"] in ("ready", "failed")
        deliveries = await webhook_sink["wait"](label, count=1, timeout=30.0)
        events_seen = {d["body"].get("event") for d in deliveries if isinstance(d["body"], dict)}
        assert events_seen & {"document.ready", "document.failed"}

        matching = next(
            d
            for d in deliveries
            if isinstance(d["body"], dict)
            and d["body"].get("event") in {"document.ready", "document.failed"}
        )
        headers = {k.lower(): v for k, v in matching["headers"].items()}
        assert headers.get("x-bigrag-event") in {"document.ready", "document.failed"}
        body_bytes = orjson.dumps(matching["body"])
        assert _verify_signature(
            created["secret"],
            body_bytes,
            headers["x-bigrag-signature"],
            headers["x-bigrag-timestamp"],
        )
    finally:
        await _cleanup_webhook(admin_client, created["id"])


async def test_replay_delivery_redelivers(
    admin_client: httpx.AsyncClient,
    webhook_sink: dict[str, Any],
) -> None:
    label = unique_name("hook")
    created = await _create_webhook(admin_client, webhook_sink["url"](label))
    try:
        resp = await admin_client.post(f"/v1/admin/webhooks/{created['id']}/test")
        assert_envelope(resp, 200)
        await webhook_sink["wait"](label, count=1)

        body = (await admin_client.get(f"/v1/admin/webhooks/{created['id']}/deliveries")).json()

        if not body.get("deliveries"):
            pytest.skip("No persisted delivery to replay (test endpoint does not persist)")

        delivery_id = body["deliveries"][0]["id"]
        before = len(await webhook_sink["received"](label))
        resp = await admin_client.post(
            f"/v1/admin/webhooks/{created['id']}/deliveries/{delivery_id}/replay"
        )
        replay_body = assert_envelope(resp, 200)
        assert replay_body["status"] in {"delivered", "failed"}
        if replay_body["status"] == "delivered":
            after = await webhook_sink["wait"](label, count=before + 1)
            assert len(after) >= before + 1
    finally:
        await _cleanup_webhook(admin_client, created["id"])


async def test_replay_via_document_ingestion(
    admin_client: httpx.AsyncClient,
    collection,
    document,
    webhook_sink: dict[str, Any],
) -> None:
    coll = await collection()
    label = unique_name("hook")
    created = await _create_webhook(
        admin_client,
        webhook_sink["url"](label),
        events=["document.ready", "document.failed"],
        collections=[coll["name"]],
    )
    try:
        await document(coll["name"], fixture="sample.txt")
        await webhook_sink["wait"](label, count=1, timeout=30.0)

        async def _persisted() -> list[dict[str, Any]]:
            r = await admin_client.get(f"/v1/admin/webhooks/{created['id']}/deliveries")
            r.raise_for_status()
            return r.json().get("deliveries", [])

        deliveries = await poll_until(
            _persisted,
            predicate=lambda items: len(items) >= 1,
            timeout=15.0,
            interval=0.5,
            description="persisted delivery",
        )

        delivery_id = deliveries[0]["id"]
        before = len(await webhook_sink["received"](label))

        resp = await admin_client.post(
            f"/v1/admin/webhooks/{created['id']}/deliveries/{delivery_id}/replay"
        )
        replay_body = assert_envelope(resp, 200)
        assert replay_body["status"] in {"delivered", "failed"}
        if replay_body["status"] == "delivered":
            received = await webhook_sink["wait"](label, count=before + 1, timeout=10.0)
            assert len(received) >= before + 1
    finally:
        await _cleanup_webhook(admin_client, created["id"])


async def test_replay_404_for_unknown_delivery(
    admin_client: httpx.AsyncClient,
    webhook_sink: dict[str, Any],
) -> None:
    label = unique_name("hook")
    created = await _create_webhook(admin_client, webhook_sink["url"](label))
    try:
        resp = await admin_client.post(
            f"/v1/admin/webhooks/{created['id']}/deliveries"
            "/00000000-0000-0000-0000-000000000000/replay"
        )
        assert resp.status_code == 404

        resp = await admin_client.post(
            f"/v1/admin/webhooks/{created['id']}/deliveries/not-a-uuid/replay"
        )
        assert resp.status_code == 404
    finally:
        await _cleanup_webhook(admin_client, created["id"])


# ---------------------------------------------------------------------------
# Deliveries listing
# ---------------------------------------------------------------------------


async def test_list_deliveries_paginates(
    admin_client: httpx.AsyncClient,
    collection,
    document,
    webhook_sink: dict[str, Any],
) -> None:
    coll = await collection()
    label = unique_name("hook")
    created = await _create_webhook(
        admin_client,
        webhook_sink["url"](label),
        events=["document.ready", "document.failed"],
        collections=[coll["name"]],
    )
    try:
        await document(coll["name"], fixture="sample.txt")
        await webhook_sink["wait"](label, count=1, timeout=30.0)

        resp = await admin_client.get(
            f"/v1/admin/webhooks/{created['id']}/deliveries",
            params={"limit": 50, "offset": 0},
        )
        body = assert_envelope(resp, 200)
        assert "deliveries" in body
        assert "total" in body
    finally:
        await _cleanup_webhook(admin_client, created["id"])


async def test_list_deliveries_404_for_unknown_webhook(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get(
        "/v1/admin/webhooks/00000000-0000-0000-0000-000000000000/deliveries"
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Behavioural: update/active/delete affect dispatch
# ---------------------------------------------------------------------------


async def test_update_events_stops_dispatch_for_unsubscribed(
    admin_client: httpx.AsyncClient,
    collection,
    document,
    webhook_sink: dict[str, Any],
) -> None:
    coll = await collection()
    label = unique_name("hook")
    created = await _create_webhook(
        admin_client,
        webhook_sink["url"](label),
        events=["document.ready", "document.failed"],
        collections=[coll["name"]],
    )
    try:
        resp = await admin_client.put(
            f"/v1/admin/webhooks/{created['id']}",
            json={"events": ["document.processing"]},
        )
        assert_envelope(resp, 200)

        await document(coll["name"], fixture="sample.txt")
        received = await webhook_sink["received"](label)
        assert all(
            (d["body"] or {}).get("event") not in {"document.ready", "document.failed"}
            for d in received
            if isinstance(d["body"], dict)
        )
    finally:
        await _cleanup_webhook(admin_client, created["id"])


async def test_delete_webhook_stops_dispatch(
    admin_client: httpx.AsyncClient,
    collection,
    document,
    webhook_sink: dict[str, Any],
) -> None:
    coll = await collection()
    label = unique_name("hook")
    created = await _create_webhook(
        admin_client,
        webhook_sink["url"](label),
        events=["document.ready", "document.failed"],
        collections=[coll["name"]],
    )
    resp = await admin_client.delete(f"/v1/admin/webhooks/{created['id']}")
    assert_envelope(resp, 200)

    await document(coll["name"], fixture="sample.txt")
    received = await webhook_sink["received"](label)
    assert received == [] or all(
        (d["body"] or {}).get("event") == "webhook.test"
        for d in received
        if isinstance(d["body"], dict)
    )


# ---------------------------------------------------------------------------
# Validation + authz
# ---------------------------------------------------------------------------


async def test_create_webhook_rejects_https_only_violation(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/admin/webhooks",
        json={"url": "http://example.com/hook", "events": ["document.ready"]},
    )
    assert resp.status_code in (400, 422), resp.text


async def test_create_webhook_rejects_unknown_event(
    admin_client: httpx.AsyncClient,
    webhook_sink: dict[str, Any],
) -> None:
    label = unique_name("hook")
    resp = await admin_client.post(
        "/v1/admin/webhooks",
        json={"url": webhook_sink["url"](label), "events": ["unknown.event"]},
    )
    assert resp.status_code in (400, 422), resp.text


async def test_webhook_endpoints_require_admin_unauth(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.get("/v1/admin/webhooks")
    assert resp.status_code == 401


async def test_webhook_endpoints_reject_api_key(
    api_key_client,
    webhook_sink: dict[str, Any],
) -> None:
    client = await api_key_client()
    resp = await client.get("/v1/admin/webhooks")
    assert resp.status_code in (401, 403)

    resp = await client.post(
        "/v1/admin/webhooks",
        json={
            "url": webhook_sink["url"](unique_name("hook")),
            "events": ["document.ready"],
        },
    )
    assert resp.status_code in (401, 403)
