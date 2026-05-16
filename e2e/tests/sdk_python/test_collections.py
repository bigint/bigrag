"""SDK contract tests for ``bigrag.CollectionsResource``.

Exercises every public method on the resource end-to-end against the
running bigRAG instance::

    list, get, create, update, delete, stats, truncate, reembed,
    stream_events

plus the :class:`bigrag.CollectionClient` wrapper's ``stats`` /
``reembed`` aliases. Response shape assertions verify the SDK returns
fully-populated ``TypedDict``-compatible dicts (the SDK uses TypedDicts,
not Pydantic models) — every documented field is present.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from bigrag import BigRAG, NotFoundError
from tests._helpers import unique_name


async def test_collections_create_returns_full_collection(
    sdk_client: Callable[..., Awaitable[BigRAG]],
) -> None:
    client = await sdk_client()
    name = unique_name("e2e")
    coll = await client.collections.create(
        {
            "name": name,
            "description": "sdk create",
            "vector_store_provider": "qdrant",
            "dimension": 1536,
            "chunk_size": 512,
            "chunk_overlap": 50,
            "chunk_strategy": "paragraph",
            "default_top_k": 10,
            "default_search_mode": "semantic",
        }
    )
    try:
        for key in (
            "id",
            "name",
            "description",
            "embedding_provider",
            "embedding_model",
            "vector_store_provider",
            "dimension",
            "chunk_size",
            "chunk_overlap",
            "chunk_strategy",
            "default_top_k",
            "default_search_mode",
            "document_count",
            "created_at",
            "updated_at",
        ):
            assert key in coll, f"missing field {key!r} in collection payload"
        assert coll["name"] == name
        assert coll["dimension"] == 1536
        assert coll["document_count"] == 0
    finally:
        await client.collections.delete(name)


async def test_collections_list_includes_created(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    created = await collection()
    listing = await client.collections.list(limit=100)
    assert "collections" in listing and "total" in listing
    assert isinstance(listing["collections"], list)
    names = [c["name"] for c in listing["collections"]]
    assert created["name"] in names


async def test_collections_list_filter_and_pagination(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    prefix = f"sdkflt_{unique_name('p')[-6:]}_"
    name = prefix + "a"
    await collection(name=name)
    listing = await client.collections.list(name=prefix, limit=10, offset=0)
    returned = [c["name"] for c in listing["collections"]]
    assert name in returned
    for n in returned:
        assert n.startswith(prefix)


async def test_collections_get_returns_dict_matching_create(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    created = await collection()
    got = await client.collections.get(created["name"])
    assert got["name"] == created["name"]
    assert got["id"] == created["id"]


async def test_collections_update_round_trip(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    created = await collection()
    updated = await client.collections.update(
        created["name"],
        {"description": "sdk update", "default_top_k": 7},
    )
    assert updated["description"] == "sdk update"
    assert updated["default_top_k"] == 7


async def test_collections_delete_then_get_raises_not_found(
    sdk_client: Callable[..., Awaitable[BigRAG]],
) -> None:
    client = await sdk_client()
    name = unique_name("sdkdel")
    await client.collections.create({"name": name, "dimension": 1536})
    status = await client.collections.delete(name)
    assert status["status"] == "ok"
    with pytest.raises(NotFoundError):
        await client.collections.get(name)


async def test_collections_stats_shape_for_empty_collection(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    created = await collection()
    stats = await client.collections.stats(created["name"])
    assert stats["collection"] == created["name"]
    assert stats["document_count"] == 0
    assert stats["total_chunks"] == 0
    assert stats["total_tokens"] == 0
    assert stats["total_size_bytes"] == 0
    assert isinstance(stats["status_counts"], dict)


async def test_collections_truncate_then_reembed(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    created = await collection()
    await document(created["name"], fixture="sample.txt")

    truncate_resp = await client.collections.truncate(created["name"])
    assert truncate_resp["status"] == "ok"

    reembed_resp = await client.collections.reembed(created["name"])
    assert reembed_resp["status"] == "ok"


async def test_collections_unknown_raises_not_found(
    sdk_client: Callable[..., Awaitable[BigRAG]],
) -> None:
    client = await sdk_client()
    missing = unique_name("missing")
    with pytest.raises(NotFoundError):
        await client.collections.get(missing)
    with pytest.raises(NotFoundError):
        await client.collections.stats(missing)
    with pytest.raises(NotFoundError):
        await client.collections.delete(missing)
    with pytest.raises(NotFoundError):
        await client.collections.update(missing, {"description": "noop"})
    with pytest.raises(NotFoundError):
        await client.collections.truncate(missing)
    with pytest.raises(NotFoundError):
        await client.collections.reembed(missing)


async def test_collection_client_stats_and_reembed_proxy(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    created = await collection()
    scoped = client.collection(created["name"])
    stats = await scoped.stats()
    assert stats["collection"] == created["name"]
    reembed = await scoped.reembed()
    assert reembed["status"] == "ok"


async def test_collections_stream_events_returns_async_iterator(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    """Smoke-test the SSE generator shape without consuming the stream
    indefinitely. We expect at least one event (the initial snapshot)
    within a short timeout."""
    import asyncio

    client = await sdk_client()
    created = await collection()
    events_gen = client.collections.stream_events(created["name"])
    try:
        event = await asyncio.wait_for(events_gen.__anext__(), timeout=5.0)
        assert isinstance(event, dict)
        assert "event" in event and "data" in event
    finally:
        await events_gen.aclose()
