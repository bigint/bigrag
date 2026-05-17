"""End-to-end tests for bigrag.routers.admin_audit.

Endpoints covered:
- GET /v1/admin/audit (list + filter by action / actor_id / resource_type + pagination)
"""

from __future__ import annotations

import httpx

from tests._helpers import assert_envelope, poll_until, unique_name


async def _whoami_id(admin_client: httpx.AsyncClient) -> str:
    resp = await admin_client.get("/v1/auth/whoami")
    assert_envelope(resp, 200)
    body = resp.json()
    # /v1/auth/whoami returns user_id at the top level (no nested "user").
    return body.get("user_id") or body.get("user", body).get("id")


async def test_audit_requires_admin(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.get("/v1/admin/audit")
    assert resp.status_code == 401


async def test_audit_rejects_api_key(api_key_client) -> None:
    client = await api_key_client()
    resp = await client.get("/v1/admin/audit")
    assert resp.status_code in (401, 403)


async def test_audit_records_api_key_creation(
    admin_client: httpx.AsyncClient,
    api_key,
) -> None:
    key = await api_key(name=unique_name("audit"))
    resp = await admin_client.get(
        "/v1/admin/audit",
        params={"action": "api_key.create", "limit": 100},
    )
    body = assert_envelope(resp, 200)
    found = next(
        (e for e in body["entries"] if e["resource_id"] == key["id"]),
        None,
    )
    assert found is not None, f"audit entry for api_key.create {key['id']!r} not found"
    assert found["action"] == "api_key.create"
    assert found["resource_type"] == "api_key"
    assert found["created_at"]


async def test_audit_filter_by_action_only_returns_matches(
    admin_client: httpx.AsyncClient,
    api_key,
) -> None:
    await api_key(name=unique_name("audit"))

    resp = await admin_client.get(
        "/v1/admin/audit",
        params={"action": "api_key.create", "limit": 50, "include_total": "true"},
    )
    body = assert_envelope(resp, 200)
    assert body["total"] >= 1
    for entry in body["entries"]:
        assert entry["action"] == "api_key.create"


async def test_audit_filter_by_resource_type(
    admin_client: httpx.AsyncClient,
    api_key,
) -> None:
    await api_key(name=unique_name("audit"))

    resp = await admin_client.get(
        "/v1/admin/audit",
        params={"resource_type": "api_key", "limit": 50},
    )
    body = assert_envelope(resp, 200)
    for entry in body["entries"]:
        assert entry["resource_type"] == "api_key"


async def test_audit_filter_by_actor_id(
    admin_client: httpx.AsyncClient,
    api_key,
) -> None:
    actor_id = await _whoami_id(admin_client)
    await api_key(name=unique_name("audit"))

    resp = await admin_client.get(
        "/v1/admin/audit",
        params={"actor_id": actor_id, "limit": 50},
    )
    body = assert_envelope(resp, 200)
    # Some system-emitted audit entries have a null actor; the filter narrows
    # to the requested actor but may also return system entries.
    for entry in body["entries"]:
        assert entry["actor_id"] in (actor_id, None)


async def test_audit_filter_invalid_actor_id(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.get(
        "/v1/admin/audit", params={"actor_id": "not-a-uuid"}
    )
    assert resp.status_code == 400


async def test_audit_pagination(
    admin_client: httpx.AsyncClient,
    api_key,
) -> None:
    for _ in range(3):
        await api_key(name=unique_name("audit"))

    resp_first = await admin_client.get(
        "/v1/admin/audit", params={"limit": 2, "offset": 0}
    )
    first_page = assert_envelope(resp_first, 200)
    assert len(first_page["entries"]) <= 2
    assert "total" in first_page

    resp_second = await admin_client.get(
        "/v1/admin/audit", params={"limit": 2, "offset": 2}
    )
    second_page = assert_envelope(resp_second, 200)
    first_ids = {e["id"] for e in first_page["entries"]}
    second_ids = {e["id"] for e in second_page["entries"]}
    assert not (first_ids & second_ids)


async def test_audit_entry_shape(
    admin_client: httpx.AsyncClient,
    api_key,
) -> None:
    await api_key(name=unique_name("audit"))
    resp = await admin_client.get("/v1/admin/audit", params={"limit": 1})
    body = assert_envelope(resp, 200)
    assert body["entries"], "expected at least one audit entry"
    entry = body["entries"][0]
    for key in (
        "id",
        "action",
        "resource_type",
        "metadata",
        "created_at",
    ):
        assert key in entry, f"missing {key!r} in audit entry: {entry!r}"


async def test_audit_records_webhook_create_and_delete(
    admin_client: httpx.AsyncClient,
    webhook_sink,
) -> None:
    label = unique_name("hook")
    resp = await admin_client.post(
        "/v1/admin/webhooks",
        json={
            "url": webhook_sink["url"](label),
            "events": ["document.ready"],
        },
    )
    created = assert_envelope(resp, 201)

    async def _fetch(action: str) -> dict:
        r = await admin_client.get(
            "/v1/admin/audit",
            params={"action": action, "limit": 50},
        )
        return assert_envelope(r, 200)

    try:
        # audit.record uses safe_create_task → polling absorbs the race.
        await poll_until(
            lambda: _fetch("webhook.create"),
            predicate=lambda b: any(
                e["resource_id"] == created["id"] for e in b["entries"]
            ),
            timeout=10.0,
            interval=0.3,
            description=f"audit webhook.create entry for {created['id']}",
        )
    finally:
        await admin_client.delete(f"/v1/admin/webhooks/{created['id']}")

    await poll_until(
        lambda: _fetch("webhook.delete"),
        predicate=lambda b: any(
            e["resource_id"] == created["id"] for e in b["entries"]
        ),
        timeout=10.0,
        interval=0.3,
        description=f"audit webhook.delete entry for {created['id']}",
    )
