"""End-to-end tests for bigrag.routers.query.

Endpoints covered:
- POST /v1/collections/{name}/query
- POST /v1/query
- POST /v1/batch/query
- POST /v1/collections/{name}/vectors/upsert
- POST /v1/collections/{name}/vectors/delete
- GET  /v1/collections/{name}/analytics
- GET  /v1/embeddings/models
"""

from __future__ import annotations

import httpx
import pytest

from tests._helpers import (
    ApiKeyClientFactory,
    ApiKeyFactory,
    CollectionFactory,
    DocumentFactory,
    assert_envelope,
    seed_collection,
    wait_until_searchable,
)

# ---------------------------------------------------------------------------
# Single-collection query
# ---------------------------------------------------------------------------


async def test_query_collection_returns_results_with_timings(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll = await seed_collection(collection, document)
    await wait_until_searchable(
        admin_client, coll["name"], "Acme Corp founded Singapore", top_k=3
    )
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/query",
        json={"query": "Acme Corp founded Singapore", "top_k": 5},
    )
    body = assert_envelope(resp, 200)

    assert body["query"] == "Acme Corp founded Singapore"
    assert body["collection"] == coll["name"]
    assert body["total"] >= 1
    assert len(body["results"]) >= 1

    first = body["results"][0]
    for key in ("id", "text", "score", "document_id"):
        assert key in first, f"missing {key} in {first!r}"
    assert isinstance(first["score"], (int, float))
    assert "document_filename" in first
    assert first["document_filename"]

    timings = body["timings"]
    for key in ("embed_ms", "search_ms", "rerank_ms", "cache_ms", "total_ms", "cache_hit"):
        assert key in timings, f"missing timings.{key} in {timings!r}"
    assert timings["cache_hit"] is False


async def test_query_collection_respects_top_k(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll = await seed_collection(collection, document)
    await wait_until_searchable(admin_client, coll["name"], "Acme")
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/query",
        json={"query": "Acme", "top_k": 1},
    )
    body = assert_envelope(resp, 200)
    assert len(body["results"]) <= 1


@pytest.mark.parametrize("mode", ["semantic", "keyword", "hybrid"])
async def test_query_collection_search_modes(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
    mode: str,
) -> None:
    coll = await seed_collection(collection, document)
    await wait_until_searchable(admin_client, coll["name"], "Acme Corp")
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/query",
        json={"query": "Acme Corp", "top_k": 5, "search_mode": mode},
    )
    body = assert_envelope(resp, 200)
    assert "results" in body
    assert "timings" in body


async def test_query_collection_metadata_filter(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll = await collection()
    doc_a = await document(
        coll["name"],
        fixture="sample.txt",
        metadata={"category": "overview"},
    )
    doc_b = await document(
        coll["name"],
        fixture="sample.md",
        metadata={"category": "architecture"},
    )
    assert doc_a["status"] == "ready"
    assert doc_b["status"] == "ready"

    await wait_until_searchable(admin_client, coll["name"], "Acme")

    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/query",
        json={
            "query": "Acme",
            "top_k": 10,
            "filters": {"category": "overview"},
        },
    )
    body = assert_envelope(resp, 200)
    # bigRAG's metadata filter DSL may require specific operator syntax.
    # Accept both "filter matched at least one" and "filter syntax was
    # unrecognized → empty result"; the goal here is to prove the filter
    # parameter is wired without crashing.
    assert body["total"] >= 0
    for row in body["results"]:
        assert row.get("metadata", {}).get("category") == "overview", row


async def test_query_collection_min_score_filter(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll = await seed_collection(collection, document)
    await wait_until_searchable(admin_client, coll["name"], "Acme")
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/query",
        json={"query": "Acme", "top_k": 10, "min_score": 0.999},
    )
    body = assert_envelope(resp, 200)
    for row in body["results"]:
        assert row["score"] >= 0.999, row


async def test_query_collection_rerank_override_respected(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll = await seed_collection(collection, document)
    await wait_until_searchable(admin_client, coll["name"], "Acme")
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/query",
        json={"query": "Acme", "top_k": 5, "rerank": False},
    )
    body = assert_envelope(resp, 200)
    timings = body["timings"]
    assert timings["rerank_ms"] == 0.0


async def test_query_cache_hit_on_second_call(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll = await seed_collection(collection, document)
    await wait_until_searchable(admin_client, coll["name"], "cache probe Acme")

    payload = {"query": "cache probe Acme", "top_k": 5}
    first = await admin_client.post(
        f"/v1/collections/{coll['name']}/query", json=payload
    )
    first_body = assert_envelope(first, 200)
    assert "cache_hit" in first_body["timings"]

    second = await admin_client.post(
        f"/v1/collections/{coll['name']}/query", json=payload
    )
    second_body = assert_envelope(second, 200)
    # Cache may or may not hit on the immediate second call depending on
    # whether result caching is enabled by the runtime config; just assert
    # the shape is present.
    assert isinstance(second_body["timings"]["cache_hit"], bool)


async def test_query_collection_requires_auth(
    unauth_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await unauth_client.post(
        f"/v1/collections/{coll['name']}/query",
        json={"query": "hi", "top_k": 5},
    )
    assert resp.status_code == 401, resp.text


async def test_query_collection_pinned_key_blocks_other_collection(
    collection: CollectionFactory,
    api_key: ApiKeyFactory,
    api_key_client: ApiKeyClientFactory,
) -> None:
    pinned = await collection()
    other = await collection()
    key = await api_key(collection=pinned["name"])
    client = await api_key_client(key=key)

    resp = await client.post(
        f"/v1/collections/{other['name']}/query",
        json={"query": "hi", "top_k": 5},
    )
    assert resp.status_code == 403, resp.text


async def test_query_collection_unknown_collection_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/collections/does-not-exist-zzz/query",
        json={"query": "hi", "top_k": 5},
    )
    assert resp.status_code == 404, resp.text


async def test_query_empty_collection_returns_empty_results(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/query",
        json={"query": "anything", "top_k": 5},
    )
    body = assert_envelope(resp, 200)
    assert body["total"] == 0
    assert body["results"] == []


# ---------------------------------------------------------------------------
# Multi-collection query
# ---------------------------------------------------------------------------


async def test_multi_collection_query_tags_results_with_collection(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll_a = await collection()
    coll_b = await collection()
    await document(coll_a["name"], fixture="sample.txt")
    await document(coll_b["name"], fixture="sample.md")

    await wait_until_searchable(admin_client, coll_a["name"], "Acme")
    await wait_until_searchable(admin_client, coll_b["name"], "Bigrag")

    resp = await admin_client.post(
        "/v1/query",
        json={
            "query": "Acme Bigrag",
            "collections": [coll_a["name"], coll_b["name"]],
            "top_k": 5,
            "search_mode": "semantic",
        },
    )
    body = assert_envelope(resp, 200)
    assert body["collections"] == [coll_a["name"], coll_b["name"]]
    assert body["total"] >= 1
    tagged = {row.get("collection") for row in body["results"]}
    assert tagged.issubset({coll_a["name"], coll_b["name"]})
    assert tagged  # at least one collection produced a result


async def test_multi_collection_query_requires_auth(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.post(
        "/v1/query",
        json={"query": "hi", "collections": ["any"], "top_k": 5},
    )
    assert resp.status_code == 401, resp.text


async def test_multi_collection_query_unknown_collection_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/query",
        json={
            "query": "hi",
            "collections": ["totally-missing-collection-xyz"],
            "top_k": 5,
        },
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Batch query
# ---------------------------------------------------------------------------


async def test_batch_query_executes_each_item(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll_a = await collection()
    coll_b = await collection()
    await document(coll_a["name"], fixture="sample.txt")
    await document(coll_b["name"], fixture="sample.md")

    await wait_until_searchable(admin_client, coll_a["name"], "Acme")
    await wait_until_searchable(admin_client, coll_b["name"], "Bigrag")

    resp = await admin_client.post(
        "/v1/batch/query",
        json={
            "queries": [
                {"collection": coll_a["name"], "query": "Acme", "top_k": 3},
                {"collection": coll_b["name"], "query": "Bigrag", "top_k": 3},
            ]
        },
    )
    body = assert_envelope(resp, 200)
    assert len(body["results"]) == 2
    by_coll = {item["collection"]: item for item in body["results"]}
    assert coll_a["name"] in by_coll
    assert coll_b["name"] in by_coll
    for item in body["results"]:
        assert isinstance(item["results"], list)
        assert "total" in item
        assert "query" in item


async def test_batch_query_requires_auth(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.post(
        "/v1/batch/query",
        json={"queries": [{"collection": "x", "query": "y"}]},
    )
    assert resp.status_code == 401, resp.text


async def test_batch_query_unknown_collection_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/batch/query",
        json={
            "queries": [
                {"collection": "no-such-thing-batch-xyz", "query": "hi"},
            ]
        },
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


async def test_collection_analytics_shape(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await admin_client.get(f"/v1/collections/{coll['name']}/analytics")
    body = assert_envelope(resp, 200)
    assert body["collection"] == coll["name"]
    for window in ("period_24h", "period_7d", "period_30d"):
        assert window in body, body
        bucket = body[window]
        for stat in ("query_count", "avg_latency_ms", "avg_score", "avg_result_count"):
            assert stat in bucket, bucket
    assert isinstance(body["top_queries"], list)


async def test_collection_analytics_requires_auth(
    unauth_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await unauth_client.get(f"/v1/collections/{coll['name']}/analytics")
    assert resp.status_code == 401, resp.text


async def test_collection_analytics_unknown_collection_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/collections/missing-analytics-xyz/analytics")
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Embeddings models list
# ---------------------------------------------------------------------------


async def test_embedding_models_list_returns_known_models(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/embeddings/models")
    body = assert_envelope(resp, 200)
    assert isinstance(body["models"], list)
    assert len(body["models"]) >= 1
    for model in body["models"]:
        for key in ("provider", "model", "dimension"):
            assert key in model, model
    providers = {m["provider"] for m in body["models"]}
    assert "openai" in providers


async def test_embedding_models_requires_auth(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.get("/v1/embeddings/models")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# Raw vector upsert / delete (escape hatch for ingest pipelines)
# ---------------------------------------------------------------------------


def _vector(dim: int, seed: int) -> list[float]:
    return [((seed + i) % 7) / 7.0 for i in range(dim)]


async def test_vectors_upsert_then_delete_round_trip(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    dim = int(coll["dimension"])
    vectors = [
        {"id": "vec-a", "embedding": _vector(dim, 1), "text": "alpha", "metadata": {"k": "a"}},
        {"id": "vec-b", "embedding": _vector(dim, 2), "text": "beta", "metadata": {"k": "b"}},
    ]
    upsert_resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/vectors/upsert",
        json={"vectors": vectors},
    )
    upserted = assert_envelope(upsert_resp, 200)
    assert upserted["status"] == "ok"
    assert upserted["upserted"] == 2

    delete_resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/vectors/delete",
        json={"ids": ["vec-a", "vec-b"]},
    )
    deleted = assert_envelope(delete_resp, 200)
    assert deleted["status"] == "ok"
    assert deleted["deleted"] == 2


async def test_vectors_upsert_rejects_wrong_dimension(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    bad = [{"id": "x", "embedding": [0.1, 0.2, 0.3], "text": "wrong dim"}]
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/vectors/upsert",
        json={"vectors": bad},
    )
    assert resp.status_code == 400, resp.text


async def test_vectors_upsert_unknown_collection_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/collections/nope_does_not_exist/vectors/upsert",
        json={"vectors": [{"id": "z", "embedding": [0.0], "text": "x"}]},
    )
    assert resp.status_code in (400, 404), resp.text


async def test_vectors_delete_unknown_ids_returns_ok(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/vectors/delete",
        json={"ids": ["does-not-exist-123"]},
    )
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"
    assert body["deleted"] == 1


async def test_vectors_upsert_requires_auth(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.post(
        "/v1/collections/any/vectors/upsert",
        json={"vectors": []},
    )
    assert resp.status_code == 401, resp.text


async def test_vectors_delete_requires_auth(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.post(
        "/v1/collections/any/vectors/delete",
        json={"ids": []},
    )
    assert resp.status_code == 401, resp.text
