"""End-to-end tests for bigrag.routers.collections.

Endpoints covered:
- POST   /v1/collections
- GET    /v1/collections
- GET    /v1/collections/{name}
- PUT    /v1/collections/{name}
- DELETE /v1/collections/{name}
- GET    /v1/collections/{name}/stats
- POST   /v1/collections/{name}/reembed
- POST   /v1/collections/{name}/truncate
- POST   /v1/collections/{name}/events/token
- GET    /v1/collections/{name}/events  (token endpoint only here; SSE
  stream itself is exercised by tests/api/test_sse_events.py — we only
  smoke-check that an unknown collection returns 404 via the token route)

Authorization checks:
- 401 unauthenticated
- 403 when an API key lacks the required scope
- 403 when a collection-pinned key targets a different collection
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from tests._helpers import assert_envelope, unique_name

# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_collection_returns_201_with_defaults(
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    assert coll["name"].startswith("e2e_")
    assert coll["dimension"] == 1536
    assert coll["embedding_model"] == "text-embedding-3-small"
    assert coll["embedding_provider"] == "openai_compatible"
    assert coll["chunk_size"] == 512
    assert coll["chunk_overlap"] == 50
    assert coll["chunk_strategy"] == "paragraph"
    assert coll["default_top_k"] == 10
    assert coll["default_search_mode"] == "semantic"
    assert coll["document_count"] == 0


async def test_create_duplicate_name_returns_409(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    first = await collection()
    resp = await admin_client.post(
        "/v1/collections",
        json={"name": first["name"], "dimension": 1536},
    )
    assert resp.status_code == 409, resp.text


async def test_create_invalid_dimension_below_min_returns_422(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/collections",
        json={
            "name": unique_name("e2e"),
            "chunk_size": 32,  # below schema minimum of 64
            "dimension": 1536,
        },
    )
    assert resp.status_code == 422, resp.text


async def test_create_invalid_chunk_overlap_returns_422(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/collections",
        json={
            "name": unique_name("e2e"),
            "chunk_size": 256,
            "chunk_overlap": 256,  # must be < chunk_size
            "dimension": 1536,
        },
    )
    assert resp.status_code == 422, resp.text


async def test_create_bad_embedding_credentials_returns_422(
    admin_client: httpx.AsyncClient,
) -> None:
    """A clearly-bogus API key should be rejected by credential verification."""
    name = unique_name("e2e")
    resp = await admin_client.post(
        "/v1/collections",
        json={
            "name": name,
            "embedding_provider": "openai_compatible",
            "embedding_model": "text-embedding-3-small",
            "embedding_api_key": "sk-definitely-not-valid",
            "embedding_base_url": "http://127.0.0.1:1/no-such-endpoint",
            "dimension": 1536,
        },
    )
    assert resp.status_code in (422, 400, 502), resp.text


async def test_create_invalid_name_pattern_returns_422(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/collections",
        json={"name": "1-starts-with-digit", "dimension": 1536},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_list_returns_envelope_with_total(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    await collection()
    resp = await admin_client.get("/v1/collections", params={"include_total": "true"})
    body = assert_envelope(resp, 200)
    assert "collections" in body
    assert "total" in body
    assert body["total"] >= 1
    assert isinstance(body["collections"], list)


async def test_list_pagination_limit_one_returns_one_item(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    await collection()
    await collection()
    resp = await admin_client.get("/v1/collections", params={"limit": 1, "offset": 0})
    body = assert_envelope(resp, 200)
    assert len(body["collections"]) == 1


async def test_list_filter_by_name_prefix_matches(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    prefix = f"prefixtest_{unique_name('p')[-6:]}_"
    name = prefix + "a"
    await collection(name=name)
    resp = await admin_client.get("/v1/collections", params={"name": prefix})
    body = assert_envelope(resp, 200)
    returned = [c["name"] for c in body["collections"]]
    assert name in returned
    for n in returned:
        assert n.startswith(prefix)


# ---------------------------------------------------------------------------
# Get / 404
# ---------------------------------------------------------------------------


async def test_get_collection_returns_full_payload(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.get(f"/v1/collections/{coll['name']}")
    body = assert_envelope(resp, 200)
    assert body["name"] == coll["name"]
    assert body["id"] == coll["id"]


async def test_get_unknown_collection_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get(f"/v1/collections/{unique_name('missing')}")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Update / Delete
# ---------------------------------------------------------------------------


async def test_update_collection_changes_description_and_top_k(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.put(
        f"/v1/collections/{coll['name']}",
        json={
            "description": "updated by e2e",
            "default_top_k": 25,
            "chunk_strategy": "recursive",
        },
    )
    body = assert_envelope(resp, 200)
    assert body["description"] == "updated by e2e"
    assert body["default_top_k"] == 25
    assert body["chunk_strategy"] == "recursive"


async def test_update_unknown_collection_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.put(
        f"/v1/collections/{unique_name('missing')}",
        json={"description": "noop"},
    )
    assert resp.status_code == 404, resp.text


async def test_delete_collection_removes_it(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.delete(f"/v1/collections/{coll['name']}")
    assert resp.status_code == 200, resp.text

    follow_up = await admin_client.get(f"/v1/collections/{coll['name']}")
    assert follow_up.status_code == 404, follow_up.text


async def test_delete_collection_also_removes_documents(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")

    resp = await admin_client.delete(f"/v1/collections/{coll['name']}")
    assert resp.status_code == 200, resp.text

    follow_up = await admin_client.get(f"/v1/collections/{coll['name']}/documents/{doc['id']}")
    assert follow_up.status_code == 404, follow_up.text


async def test_delete_unknown_collection_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.delete(f"/v1/collections/{unique_name('missing')}")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


async def test_stats_shape_for_empty_collection(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.get(f"/v1/collections/{coll['name']}/stats")
    body = assert_envelope(resp, 200)
    assert body["collection"] == coll["name"]
    assert body["document_count"] == 0
    assert body["total_chunks"] == 0
    assert body["total_tokens"] == 0
    assert body["total_size_bytes"] == 0
    assert body["status_counts"] == {
        "ready": 0,
        "pending": 0,
        "processing": 0,
        "failed": 0,
    }


async def test_stats_counts_a_ready_document(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    assert doc["status"] == "ready"

    resp = await admin_client.get(f"/v1/collections/{coll['name']}/stats")
    body = assert_envelope(resp, 200)
    assert body["document_count"] == 1
    assert body["total_chunks"] >= 1
    assert body["status_counts"]["ready"] == 1


async def test_stats_unknown_collection_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get(f"/v1/collections/{unique_name('missing')}/stats")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Reembed / Truncate
# ---------------------------------------------------------------------------


async def test_reembed_kicks_off_for_existing_collection(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")

    resp = await admin_client.post(f"/v1/collections/{coll['name']}/reembed")
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"
    assert "re-embedding" in body["message"]


async def test_reembed_unknown_collection_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(f"/v1/collections/{unique_name('missing')}/reembed")
    assert resp.status_code == 404, resp.text


async def test_truncate_removes_documents_but_keeps_collection(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")

    resp = await admin_client.post(f"/v1/collections/{coll['name']}/truncate")
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"

    stats = await admin_client.get(f"/v1/collections/{coll['name']}/stats")
    stats_body = assert_envelope(stats, 200)
    assert stats_body["document_count"] == 0


async def test_truncate_unknown_collection_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(f"/v1/collections/{unique_name('missing')}/truncate")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Event token (SSE stream covered elsewhere)
# ---------------------------------------------------------------------------


async def test_event_token_returns_short_lived_token(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.post(f"/v1/collections/{coll['name']}/events/token")
    body = assert_envelope(resp, 200)
    assert isinstance(body["token"], str) and len(body["token"]) > 0
    assert isinstance(body["expires_in"], int) and body["expires_in"] > 0


async def test_event_token_unknown_collection_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(f"/v1/collections/{unique_name('missing')}/events/token")
    assert resp.status_code == 404, resp.text


async def test_collection_events_unknown_collection_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    """Hit the SSE GET endpoint just enough to verify it 404s for unknown
    collections without consuming the stream (full SSE flow is covered by
    test_sse_events.py)."""
    resp = await admin_client.get(f"/v1/collections/{unique_name('missing')}/events")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


async def test_list_collections_requires_auth(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.get("/v1/collections")
    assert resp.status_code == 401, resp.text


async def test_create_collection_requires_auth(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.post(
        "/v1/collections",
        json={"name": unique_name("e2e"), "dimension": 1536},
        headers={"Origin": "http://localhost:4000"},
    )
    assert resp.status_code == 401, resp.text


async def test_delete_collection_requires_auth(
    unauth_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await unauth_client.delete(
        f"/v1/collections/{coll['name']}",
        headers={"Origin": "http://localhost:4000"},
    )
    assert resp.status_code == 401, resp.text


async def test_api_key_without_collection_write_scope_cannot_create(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    client = await api_key_client(scopes=["query:read"])
    resp = await client.post(
        "/v1/collections",
        json={"name": unique_name("e2e"), "dimension": 1536},
    )
    assert resp.status_code == 403, resp.text


async def test_api_key_pinned_to_collection_cannot_create_collections(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    pinned = await collection()
    client = await api_key_client(collection=pinned["name"])
    resp = await client.post(
        "/v1/collections",
        json={"name": unique_name("e2e"), "dimension": 1536},
    )
    assert resp.status_code == 403, resp.text


async def test_api_key_pinned_to_one_collection_cannot_read_another(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    pinned = await collection()
    other = await collection()
    client = await api_key_client(collection=pinned["name"])

    resp = await client.get(f"/v1/collections/{other['name']}")
    assert resp.status_code == 403, resp.text


async def test_api_key_pinned_can_read_its_own_collection(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    pinned = await collection()
    client = await api_key_client(collection=pinned["name"])

    resp = await client.get(f"/v1/collections/{pinned['name']}")
    body = assert_envelope(resp, 200)
    assert body["name"] == pinned["name"]
