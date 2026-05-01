from __future__ import annotations

import asyncio
import warnings
from types import SimpleNamespace

import pytest
from qdrant_client import AsyncQdrantClient

from bigrag.services import vector_store as vector_store_module
from bigrag.services._retrieval_filters import build_filter
from bigrag.services.vector_store import VectorStore


def test_connect_passes_qdrant_config(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeQdrantClient:
        def __init__(self, **kwargs) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(vector_store_module, "AsyncQdrantClient", FakeQdrantClient)

    store = VectorStore("http://qdrant:6333")
    store.configure(
        "http://qdrant:6333",
        api_key="secret",
        connect_timeout_seconds=7,
    )
    store.connect()

    assert calls == [{"url": "http://qdrant:6333", "api_key": "secret", "timeout": 7.0}]


def test_zero_connect_timeout_disables_qdrant_timeout(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeQdrantClient:
        def __init__(self, **kwargs) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(vector_store_module, "AsyncQdrantClient", FakeQdrantClient)

    store = VectorStore("http://qdrant:6333")
    store.configure("http://qdrant:6333", connect_timeout_seconds=0)
    store.connect()

    assert calls == [{"url": "http://qdrant:6333", "api_key": None, "timeout": None}]


def test_external_ids_are_mapped_to_stable_qdrant_uuid() -> None:
    store = VectorStore()

    first = store._point_id("bigrag_docs", "document-id_12")
    second = store._point_id("bigrag_docs", "document-id_12")
    other_collection = store._point_id("bigrag_other", "document-id_12")

    assert first == second
    assert first != other_collection


def test_insert_preserves_external_id_in_payload() -> None:
    captured = {}

    class FakeQdrantClient:
        async def upsert(self, **kwargs):
            captured.update(kwargs)

    store = VectorStore()
    store.client = FakeQdrantClient()  # type: ignore[assignment]

    count = asyncio.run(
        store.insert(
            collection="docs",
            ids=["custom-id"],
            document_ids=["doc-1"],
            chunk_indices=[2],
            texts=["hello"],
            embeddings=[[0.1, 0.2, 0.3]],
            metadata=[{"page_no": 4}],
        )
    )

    point = captured["points"][0]
    assert count == 1
    assert point.payload["id"] == "custom-id"
    assert point.payload["document_id"] == "doc-1"
    assert point.payload["chunk_index"] == 2
    assert point.payload["page_no"] == 4


def test_qdrant_local_round_trip_search_filter_and_delete() -> None:
    async def run() -> None:
        store = VectorStore()
        store.client = AsyncQdrantClient(":memory:")  # type: ignore[assignment]

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Payload indexes have no effect.*")
            await store.create_collection("docs", dimension=3, tenant_field="tenant_id")
        await store.insert(
            collection="docs",
            ids=["doc-1_0", "doc-2_0"],
            document_ids=["doc-1", "doc-2"],
            chunk_indices=[0, 0],
            texts=["alpha revenue forecast", "beta support guide"],
            embeddings=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            metadata=[{"tenant_id": "acme"}, {"tenant_id": "beta"}],
        )

        hits = await store.search(
            "docs",
            [1.0, 0.0, 0.0],
            top_k=2,
            filters=build_filter({"tenant_id": "acme"}),
        )
        assert [hit["id"] for hit in hits] == ["doc-1_0"]

        chunks, total = await store.get_chunks("docs", "doc-1")
        assert total == 1
        assert chunks[0]["text"] == "alpha revenue forecast"

        text_hits = await store.text_search(
            "docs",
            ["revenue"],
            top_k=5,
            filters=build_filter({"tenant_id": "acme"}),
        )
        assert [hit["id"] for hit in text_hits] == ["doc-1_0"]

        await store.delete_by_ids("docs", ["doc-1_0"])
        hits = await store.search(
            "docs",
            [1.0, 0.0, 0.0],
            top_k=2,
            filters=build_filter({"tenant_id": "acme"}),
        )
        assert hits == []
        await store.close()

    asyncio.run(run())


def test_build_filter_rejects_unknown_operators() -> None:
    with pytest.raises(ValueError, match="Unsupported filter operator"):
        build_filter({"tenant_id": {"$nin": ["acme"]}})


def test_build_filter_rejects_empty_operator_objects() -> None:
    with pytest.raises(ValueError, match="has no operators"):
        build_filter({"tenant_id": {}})


def test_get_chunks_follows_all_qdrant_scroll_pages() -> None:
    class FakeQdrantClient:
        def __init__(self) -> None:
            self.offsets = []

        async def collection_exists(self, _collection_name: str) -> bool:
            return True

        async def scroll(self, **kwargs):
            self.offsets.append(kwargs.get("offset"))
            if kwargs.get("offset") is None:
                return (
                    [
                        SimpleNamespace(
                            id="point-0",
                            payload={
                                "id": "doc-1_0",
                                "document_id": "doc-1",
                                "chunk_index": 0,
                                "text": "first",
                            },
                        ),
                        SimpleNamespace(
                            id="point-1",
                            payload={
                                "id": "doc-1_1",
                                "document_id": "doc-1",
                                "chunk_index": 1,
                                "text": "second",
                            },
                        ),
                    ],
                    "next-page",
                )
            return (
                [
                    SimpleNamespace(
                        id="point-2",
                        payload={
                            "id": "doc-1_2",
                            "document_id": "doc-1",
                            "chunk_index": 2,
                            "text": "third",
                        },
                    )
                ],
                None,
            )

    async def run() -> None:
        store = VectorStore()
        client = FakeQdrantClient()
        store.client = client  # type: ignore[assignment]

        chunks, total = await store.get_chunks("docs", "doc-1", limit=2, offset=1)

        assert client.offsets == [None, "next-page"]
        assert total == 3
        assert [chunk["text"] for chunk in chunks] == ["second", "third"]

    asyncio.run(run())
