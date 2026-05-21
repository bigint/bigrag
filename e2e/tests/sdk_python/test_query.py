"""SDK contract tests for ``bigrag.QueryResource``.

Touches every public method on the resource::

    query, multi_query, batch_query

plus the :meth:`bigrag.CollectionClient.query` wrapper. Verifies the
returned dicts conform to the typed response shape and that filters,
top_k, search_mode, and min_score round-trip through to the server.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from bigrag import BigRAG, NotFoundError

from tests._helpers import unique_name


async def test_query_single_collection_returns_typed_results(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")

    response = await client.queries.query(
        coll["name"],
        {"query": "sample", "top_k": 5},
    )
    assert response["query"] == "sample"
    assert response["collection"] == coll["name"]
    assert isinstance(response["results"], list)
    assert response["total"] == len(response["results"])
    if response["results"]:
        first = response["results"][0]
        for key in (
            "id",
            "text",
            "score",
            "document_id",
            "document_filename",
            "metadata",
        ):
            assert key in first
        assert isinstance(first["score"], (int, float))


async def test_query_top_k_limits_result_count(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")

    response = await client.queries.query(coll["name"], {"query": "sample", "top_k": 1})
    assert len(response["results"]) <= 1


async def test_query_search_mode_and_rerank_pass_through(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    """Server accepts the supplied search_mode without error and returns
    a valid response shape."""
    client = await sdk_client()
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")

    response = await client.queries.query(
        coll["name"],
        {
            "query": "sample",
            "top_k": 3,
            "search_mode": "semantic",
            "rerank": False,
        },
    )
    assert "results" in response


async def test_query_min_score_excludes_low_relevance(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")

    response = await client.queries.query(
        coll["name"], {"query": "sample", "min_score": 0.999, "top_k": 5}
    )
    for hit in response["results"]:
        assert hit["score"] >= 0.999


async def test_query_filters_pass_through(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    """Filters that match no document should yield an empty result set
    rather than an exception."""
    client = await sdk_client()
    coll = await collection()
    await document(coll["name"], fixture="sample.txt", metadata={"tag": "alpha"})

    response = await client.queries.query(
        coll["name"],
        {
            "query": "sample",
            "top_k": 5,
            "filters": {"tag": "definitely-not-a-real-tag"},
        },
    )
    assert response["results"] == []
    assert response["total"] == 0


async def test_query_empty_collection_returns_empty_results(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()

    response = await client.queries.query(coll["name"], {"query": "anything", "top_k": 5})
    assert response["results"] == []
    assert response["total"] == 0


async def test_multi_query_across_collections(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    a = await collection()
    b = await collection()
    await document(a["name"], fixture="sample.txt")
    await document(b["name"], fixture="sample.md")

    response = await client.queries.multi_query(
        {
            "query": "sample",
            "collections": [a["name"], b["name"]],
            "top_k": 3,
        }
    )
    assert response["query"] == "sample"
    assert set(response["collections"]) == {a["name"], b["name"]}
    assert isinstance(response["results"], list)
    if response["results"]:
        first = response["results"][0]
        assert first["collection"] in {a["name"], b["name"]}
        for key in ("id", "text", "score", "collection", "metadata"):
            assert key in first


async def test_batch_query_returns_one_item_per_request(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    a = await collection()
    b = await collection()
    await document(a["name"], fixture="sample.txt")
    await document(b["name"], fixture="sample.md")

    response = await client.queries.batch_query(
        {
            "queries": [
                {"collection": a["name"], "query": "sample", "top_k": 2},
                {"collection": b["name"], "query": "sample", "top_k": 2},
            ]
        }
    )
    assert len(response["results"]) == 2
    seen_collections = {r["collection"] for r in response["results"]}
    assert seen_collections == {a["name"], b["name"]}
    for item in response["results"]:
        assert item["query"] == "sample"
        assert "results" in item
        assert item["total"] == len(item["results"])


async def test_query_unknown_collection_raises_not_found(
    sdk_client: Callable[..., Awaitable[BigRAG]],
) -> None:
    client = await sdk_client()
    with pytest.raises(NotFoundError):
        await client.queries.query(unique_name("missing"), {"query": "x", "top_k": 1})


async def test_collection_client_query_wrapper(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")

    scoped = client.collection(coll["name"])
    response = await scoped.query({"query": "sample", "top_k": 5})
    assert response["collection"] == coll["name"]
