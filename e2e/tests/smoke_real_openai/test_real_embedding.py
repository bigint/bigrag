"""Real-OpenAI smoke test for embedding + retrieval.

This test issues exactly two real OpenAI calls:

1. one embedding call during document ingestion (a tiny ``sample.txt``)
2. one embedding call to embed the query

Total cost: roughly $0.00001 at current ``text-embedding-3-small`` rates.

The whole module is skipped unless ``BIGRAG_E2E_REAL_OPENAI=1`` (see
``conftest.py`` in this directory).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from tests._helpers import assert_envelope


async def test_real_openai_embedding_roundtrip(
    real_openai_settings: dict[str, object],
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection(dimension=int(real_openai_settings["embedding_dimension"]))
    doc = await document(coll["name"], fixture="sample.txt")
    assert doc["status"] == "ready", doc

    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/query",
        json={"query": "Where is Acme Corp headquartered?", "top_k": 3},
    )
    body = assert_envelope(resp, 200)

    results = body["results"]
    assert results, f"expected at least one result, got: {body!r}"
    assert results[0]["score"] > 0.0, f"top result has non-positive score: {results[0]!r}"
