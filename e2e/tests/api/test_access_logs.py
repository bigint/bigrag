"""End-to-end tests for bigrag.routers.admin_access.

Endpoints covered:
- GET /v1/admin/access/logs (list + filters + pagination)
- GET /v1/admin/access/overview (aggregates)

The access-log middleware only records ``RAG_ACCESS_ACTIONS`` (query.*,
chat.generate, vectors.upsert/delete, evaluation.run). We seed entries
by issuing queries against a real collection.
"""

from __future__ import annotations

import httpx

from tests._helpers import assert_envelope, poll_until, unique_name


async def _seed_query(
    admin_client: httpx.AsyncClient, collection_name: str, query: str = "hello"
) -> int:
    resp = await admin_client.post(
        f"/v1/collections/{collection_name}/query",
        json={"query": query, "top_k": 3},
    )
    return resp.status_code


async def _wait_for_action(
    admin_client: httpx.AsyncClient,
    action: str,
    *,
    timeout: float = 10.0,
) -> list[dict]:
    async def _fetch() -> list[dict]:
        r = await admin_client.get("/v1/admin/access/logs", params={"action": action, "limit": 50})
        r.raise_for_status()
        return r.json().get("entries", [])

    return await poll_until(
        _fetch,
        predicate=lambda items: len(items) >= 1,
        timeout=timeout,
        interval=0.5,
        description=f"access log entry for action={action!r}",
    )


# ---------------------------------------------------------------------------
# Authz
# ---------------------------------------------------------------------------


async def test_logs_requires_admin(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.get("/v1/admin/access/logs")
    assert resp.status_code == 401


async def test_overview_requires_admin(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.get("/v1/admin/access/overview")
    assert resp.status_code == 401


async def test_logs_rejects_api_key(api_key_client) -> None:
    client = await api_key_client()
    resp = await client.get("/v1/admin/access/logs")
    assert resp.status_code in (401, 403)


async def test_overview_rejects_api_key(api_key_client) -> None:
    client = await api_key_client()
    resp = await client.get("/v1/admin/access/overview")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# /logs
# ---------------------------------------------------------------------------


async def test_logs_returns_entries_after_query(
    admin_client: httpx.AsyncClient,
    collection,
    document,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    status = await _seed_query(admin_client, coll["name"])
    assert status in (200, 400)

    entries = await _wait_for_action(admin_client, "query.run")
    assert any(e.get("collection_name") == coll["name"] for e in entries)


async def test_logs_entry_shape(
    admin_client: httpx.AsyncClient,
    collection,
    document,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    await _seed_query(admin_client, coll["name"])
    entries = await _wait_for_action(admin_client, "query.run")

    entry = entries[0]
    for key in (
        "id",
        "action",
        "resource_type",
        "method",
        "path",
        "status_code",
        "success",
        "latency_ms",
        "created_at",
    ):
        assert key in entry, f"missing {key!r} in entry: {entry!r}"


async def test_logs_filter_by_action(
    admin_client: httpx.AsyncClient,
    collection,
    document,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    await _seed_query(admin_client, coll["name"])
    await _wait_for_action(admin_client, "query.run")

    resp = await admin_client.get(
        "/v1/admin/access/logs", params={"action": "query.run", "limit": 100}
    )
    body = assert_envelope(resp, 200)
    for entry in body["entries"]:
        assert entry["action"] == "query.run"


async def test_logs_filter_by_collection(
    admin_client: httpx.AsyncClient,
    collection,
    document,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    await _seed_query(admin_client, coll["name"])
    await _wait_for_action(admin_client, "query.run")

    async def _fetch_filtered() -> dict:
        r = await admin_client.get(
            "/v1/admin/access/logs",
            params={"collection": coll["name"], "limit": 50, "include_total": "true"},
        )
        return assert_envelope(r, 200)

    body = await poll_until(
        _fetch_filtered,
        predicate=lambda b: b["total"] >= 1,
        timeout=15.0,
        interval=0.5,
        description=f"access_log entries for collection {coll['name']!r}",
    )
    for entry in body["entries"]:
        assert entry["collection_name"] == coll["name"]


async def test_logs_filter_by_method(
    admin_client: httpx.AsyncClient,
    collection,
    document,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    await _seed_query(admin_client, coll["name"])
    await _wait_for_action(admin_client, "query.run")

    resp = await admin_client.get("/v1/admin/access/logs", params={"method": "post", "limit": 20})
    body = assert_envelope(resp, 200)
    for entry in body["entries"]:
        assert entry["method"] == "POST"


async def test_logs_filter_by_path_substring(
    admin_client: httpx.AsyncClient,
    collection,
    document,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    await _seed_query(admin_client, coll["name"])
    await _wait_for_action(admin_client, "query.run")

    resp = await admin_client.get("/v1/admin/access/logs", params={"path": "/query", "limit": 20})
    body = assert_envelope(resp, 200)
    for entry in body["entries"]:
        assert "/query" in entry["path"]


async def test_logs_filter_by_status_family_2xx(
    admin_client: httpx.AsyncClient,
    collection,
    document,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    await _seed_query(admin_client, coll["name"])
    await _wait_for_action(admin_client, "query.run")

    resp = await admin_client.get(
        "/v1/admin/access/logs", params={"status_family": "2xx", "limit": 20}
    )
    body = assert_envelope(resp, 200)
    for entry in body["entries"]:
        assert 200 <= entry["status_code"] < 300


async def test_logs_filter_by_success(
    admin_client: httpx.AsyncClient,
    collection,
    document,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    await _seed_query(admin_client, coll["name"])
    await _wait_for_action(admin_client, "query.run")

    resp = await admin_client.get("/v1/admin/access/logs", params={"success": "true", "limit": 20})
    body = assert_envelope(resp, 200)
    for entry in body["entries"]:
        assert entry["success"] is True


async def test_logs_invalid_actor_id_returns_400(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/admin/access/logs", params={"actor_id": "not-a-uuid"})
    assert resp.status_code == 400


async def test_logs_invalid_status_family_returns_422(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/admin/access/logs", params={"status_family": "9xx"})
    assert resp.status_code == 422


async def test_logs_pagination(
    admin_client: httpx.AsyncClient,
    collection,
    document,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    for i in range(3):
        await _seed_query(admin_client, coll["name"], query=unique_name(f"q{i}"))
    await _wait_for_action(admin_client, "query.run")

    page1 = (
        await admin_client.get(
            "/v1/admin/access/logs",
            params={"limit": 2, "offset": 0},
        )
    ).json()
    page2 = (
        await admin_client.get(
            "/v1/admin/access/logs",
            params={"limit": 2, "offset": 2},
        )
    ).json()
    ids1 = {e["id"] for e in page1["entries"]}
    ids2 = {e["id"] for e in page2["entries"]}
    assert not (ids1 & ids2)


# ---------------------------------------------------------------------------
# /overview
# ---------------------------------------------------------------------------


async def test_overview_shape_and_window(
    admin_client: httpx.AsyncClient,
    collection,
    document,
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")
    await _seed_query(admin_client, coll["name"])
    await _wait_for_action(admin_client, "query.run")

    resp = await admin_client.get("/v1/admin/access/overview", params={"window_days": 7})
    body = assert_envelope(resp, 200)
    for key in (
        "window_days",
        "total_events",
        "success_rate",
        "error_rate",
        "avg_latency_ms",
        "p95_latency_ms",
        "unique_users",
        "query_events",
        "by_action",
        "latency_by_action",
        "timeline",
        "recent",
    ):
        assert key in body, f"missing {key!r} in overview body"
    assert body["window_days"] == 7
    assert body["total_events"] >= 1
    assert body["query_events"] >= 1
    assert any(b["label"] == "query.run" for b in body["by_action"])


async def test_overview_default_window(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.get("/v1/admin/access/overview")
    body = assert_envelope(resp, 200)
    assert body["window_days"] == 7


async def test_overview_invalid_window_rejected(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/admin/access/overview", params={"window_days": 0})
    assert resp.status_code == 422

    resp = await admin_client.get("/v1/admin/access/overview", params={"window_days": 1000})
    assert resp.status_code == 422
