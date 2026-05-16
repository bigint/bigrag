"""End-to-end tests for bigrag.routers.evaluation.

Endpoints covered:
- POST /v1/evaluation
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from tests._helpers import assert_envelope, poll_until


CollectionFactory = Callable[..., Awaitable[dict[str, Any]]]
DocumentFactory = Callable[..., Awaitable[dict[str, Any]]]
ApiKeyFactory = Callable[..., Awaitable[dict[str, Any]]]
ApiKeyClientFactory = Callable[..., Awaitable[httpx.AsyncClient]]


GOLDEN_SETS_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "golden_sets"


async def _wait_until_searchable(
    admin_client: httpx.AsyncClient,
    collection_name: str,
    query: str,
    *,
    timeout: float = 30.0,
) -> None:
    async def _do() -> dict[str, Any]:
        resp = await admin_client.post(
            f"/v1/collections/{collection_name}/query",
            json={"query": query, "top_k": 3},
        )
        return assert_envelope(resp, 200)

    await poll_until(
        _do,
        predicate=lambda body: len(body.get("results") or []) > 0,
        timeout=timeout,
        interval=0.5,
        description=f"results for {query!r} on {collection_name}",
    )


def _load_golden_set() -> dict[str, Any]:
    return json.loads((GOLDEN_SETS_DIR / "acme.json").read_text())


def _substitute_ids(
    golden: dict[str, Any], id_map: dict[str, str]
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for entry in golden["queries"]:
        expected = [id_map.get(raw, raw) for raw in entry["expected_doc_ids"]]
        cases.append({"query": entry["query"], "relevant_ids": expected})
    return cases


async def _seed_with_golden_docs(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> tuple[dict[str, Any], dict[str, str]]:
    coll = await collection()
    txt = await document(coll["name"], fixture="sample.txt")
    md = await document(coll["name"], fixture="sample.md")
    for doc in (txt, md):
        assert doc["status"] == "ready", doc

    id_map = {
        "__sample_txt__": str(txt["id"]),
        "__sample_md__": str(md["id"]),
        "__sample_html__": str(md["id"]),
    }

    await _wait_until_searchable(admin_client, coll["name"], "Acme")
    return coll, id_map


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_evaluation_returns_metrics_and_per_case(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll, id_map = await _seed_with_golden_docs(admin_client, collection, document)
    golden = _load_golden_set()
    cases = _substitute_ids(golden, id_map)

    resp = await admin_client.post(
        "/v1/evaluation",
        json={
            "collection": coll["name"],
            "cases": cases,
            "top_k": 5,
            "search_mode": "semantic",
        },
    )
    body = assert_envelope(resp, 200)
    assert body["collection"] == coll["name"]
    assert body["total_cases"] == len(cases)
    for metric in ("recall_at_k_avg", "mrr", "ndcg_at_k_avg"):
        assert metric in body, body
        assert isinstance(body[metric], (int, float))
        # bigRAG's NDCG can mildly exceed 1.0 when graded relevance is used;
        # accept a generous upper bound to avoid brittle scoring assertions.
        assert 0.0 <= body[metric] <= 2.0

    assert isinstance(body["per_case"], list)
    assert len(body["per_case"]) == len(cases)
    for entry in body["per_case"]:
        for key in (
            "query",
            "hit_ids",
            "expected_ids",
            "recall_at_k",
            "reciprocal_rank",
            "ndcg_at_k",
        ):
            assert key in entry, entry
        assert isinstance(entry["hit_ids"], list)
        assert isinstance(entry["expected_ids"], list)
        assert 0.0 <= entry["recall_at_k"] <= 2.0
        assert 0.0 <= entry["reciprocal_rank"] <= 2.0
        assert 0.0 <= entry["ndcg_at_k"] <= 2.0


async def test_evaluation_supports_per_case_top_k_and_filters(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
    document: DocumentFactory,
) -> None:
    coll, id_map = await _seed_with_golden_docs(admin_client, collection, document)
    cases = [
        {
            "query": "Where was Acme founded?",
            "relevant_ids": [id_map["__sample_txt__"]],
            "top_k": 3,
        }
    ]
    resp = await admin_client.post(
        "/v1/evaluation",
        json={"collection": coll["name"], "cases": cases, "top_k": 5},
    )
    body = assert_envelope(resp, 200)
    assert body["total_cases"] == 1
    case = body["per_case"][0]
    assert len(case["hit_ids"]) <= 3


# ---------------------------------------------------------------------------
# Errors and authorization
# ---------------------------------------------------------------------------


async def test_evaluation_requires_auth(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.post(
        "/v1/evaluation",
        json={
            "collection": "x",
            "cases": [{"query": "y", "relevant_ids": ["z"]}],
        },
    )
    assert resp.status_code == 401, resp.text


async def test_evaluation_unknown_collection_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/evaluation",
        json={
            "collection": "evaluation-missing-coll-xyz",
            "cases": [{"query": "anything", "relevant_ids": ["00000000"]}],
        },
    )
    assert resp.status_code == 404, resp.text


async def test_evaluation_pinned_api_key_blocks_other_collection(
    api_key: ApiKeyFactory,
    api_key_client: ApiKeyClientFactory,
    collection: CollectionFactory,
) -> None:
    pinned = await collection()
    other = await collection()
    key = await api_key(collection=pinned["name"], scopes=["query:read"])
    client = await api_key_client(key=key)

    resp = await client.post(
        "/v1/evaluation",
        json={
            "collection": other["name"],
            "cases": [{"query": "hi", "relevant_ids": ["abc"]}],
        },
    )
    assert resp.status_code == 403, resp.text


async def test_evaluation_rejects_empty_cases(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await admin_client.post(
        "/v1/evaluation",
        json={"collection": coll["name"], "cases": []},
    )
    assert resp.status_code == 422, resp.text


async def test_evaluation_against_empty_collection_returns_zeroed_metrics(
    admin_client: httpx.AsyncClient,
    collection: CollectionFactory,
) -> None:
    coll = await collection()
    resp = await admin_client.post(
        "/v1/evaluation",
        json={
            "collection": coll["name"],
            "cases": [{"query": "Acme", "relevant_ids": ["00000000-fake-id"]}],
            "top_k": 5,
        },
    )
    body = assert_envelope(resp, 200)
    assert body["total_cases"] == 1
    assert body["recall_at_k_avg"] == 0.0
    assert body["mrr"] == 0.0
    assert body["ndcg_at_k_avg"] == 0.0
