from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from tests._helpers import assert_envelope, wait_until_searchable


async def test_multimodal_pdf_ingestion_stores_elements_and_query_refs(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection(multimodal_enabled=True, chunk_size=256)
    doc = await document(coll["name"], fixture="sample_multimodal.pdf")
    assert doc["status"] == "ready"
    assert doc["multimodal_element_count"] >= 1

    elements_resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents/{doc['id']}/elements"
    )
    elements_body = assert_envelope(elements_resp, 200)
    assert elements_body["total"] == doc["multimodal_element_count"]
    assert elements_body["elements"]
    kinds = {item["kind"] for item in elements_body["elements"]}
    assert kinds & {"heading", "table", "equation", "image", "text"}
    assert all(item["document_id"] == doc["id"] for item in elements_body["elements"])

    await wait_until_searchable(admin_client, coll["name"], "Revenue", top_k=3)
    text_query_resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/query",
        json={"query": "Revenue", "top_k": 3},
    )
    text_query_body = assert_envelope(text_query_resp, 200)
    assert text_query_body["results"]
    assert not any(row.get("multimodal_elements") for row in text_query_body["results"])
    assert not any(
        row.get("metadata", {}).get("multimodal_elements") for row in text_query_body["results"]
    )

    query_resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/query",
        json={"query": "Revenue", "top_k": 3, "multimodal": True},
    )
    query_body = assert_envelope(query_resp, 200)
    assert query_body["results"]
    assert any(row.get("multimodal_elements") for row in query_body["results"])


async def test_multimodal_chat_returns_source_element_refs(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection(multimodal_enabled=True, chunk_size=256)
    doc = await document(coll["name"], fixture="sample_multimodal.pdf")
    await wait_until_searchable(admin_client, coll["name"], "Revenue", top_k=3)

    resp = await admin_client.post(
        "/v1/chat",
        json={
            "collection": coll["name"],
            "message": "What does the revenue table say?",
            "stream": False,
            "top_k": 3,
            "multimodal": True,
        },
    )
    body = assert_envelope(resp, 200)
    assert body["assistant_message"]["content"]
    matching_sources = [
        source
        for source in body["sources"]
        if source.get("document_id") == doc["id"] and source.get("multimodal_elements")
    ]
    assert matching_sources
