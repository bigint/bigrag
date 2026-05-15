from __future__ import annotations

import asyncio

import pytest

import bigrag.services.vector_store.turbopuffer as turbopuffer_module
from bigrag.services._retrieval_filters import build_filter
from bigrag.services.vector_store import (
    QdrantVectorStore,
    TurbopufferVectorStore,
    VectorStore,
    VectorStoreFeatureError,
    _to_turbopuffer_filter,
)
from bigrag.services.vector_store.base import _point_id
from bigrag.services.vector_store.qdrant import _to_qdrant_filter


def test_turbopuffer_filter_translation() -> None:
    expr = build_filter(
        {"id": "chunk-1", "tenant_id": "acme", "page_no": {"$gt": 1}, "kind": {"$in": ["pdf"]}}
    )

    assert _to_turbopuffer_filter(expr) == [
        "And",
        [
            ["bigrag_id", "Eq", "chunk-1"],
            ["tenant_id", "Eq", "acme"],
            ["page_no", "Gt", 1],
            ["kind", "In", ["pdf"]],
        ],
    ]


class FakeResponse:
    def __init__(self, payload: dict | None = None, status_code: int = 200) -> None:
        self.payload = payload or {}
        self.status_code = status_code
        self.content = b"{}"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("request failed")

    def json(self) -> dict:
        return self.payload


class FakeTurbopufferClient:
    def __init__(self) -> None:
        self.posts = []
        self.gets = []
        self.deletes = []
        self.query_pages = []
        self.closed = False

    async def get(self, path: str):
        self.gets.append(path)
        return FakeResponse()

    async def post(self, path: str, json: dict):
        if "include_attributes" in json and "exclude_attributes" in json:
            raise RuntimeError("include/exclude conflict")
        self.posts.append((path, json))
        if path.endswith("/query"):
            if self.query_pages:
                return FakeResponse({"rows": self.query_pages.pop(0)})
            return FakeResponse(
                {
                    "rows": [
                        {
                            "$dist": 0.25,
                            "id": "point-1",
                            "bigrag_id": "chunk-1",
                            "text": "hello",
                            "document_id": "doc-1",
                            "chunk_index": 0,
                            "tenant_id": "acme",
                        }
                    ]
                }
            )
        return FakeResponse()

    async def delete(self, path: str):
        self.deletes.append(path)
        return FakeResponse(status_code=404)

    async def aclose(self):
        self.closed = True


def test_turbopuffer_adapter_maps_write_query_and_delete() -> None:
    asyncio.run(_test_turbopuffer_adapter_maps_write_query_and_delete())


async def _test_turbopuffer_adapter_maps_write_query_and_delete() -> None:
    store = TurbopufferVectorStore(api_key="tpuf", region="aws-us-east-1")
    fake = FakeTurbopufferClient()
    store.client = fake

    count = await store.insert("docs", ["chunk-1"], ["doc-1"], [0], ["hello"], [[0.1, 0.2]])
    results = await store.search("docs", [0.1, 0.2], filters=build_filter({"tenant_id": "acme"}))
    await store.delete_by_document("docs", "doc-1")

    assert count == 1
    assert fake.posts[0][0] == "/v2/namespaces/bigrag_docs"
    assert fake.posts[0][1]["upsert_rows"][0]["id"] == _point_id("bigrag_docs", "chunk-1")
    assert fake.posts[0][1]["upsert_rows"][0]["bigrag_id"] == "chunk-1"
    assert fake.posts[0][1]["upsert_rows"][0]["document_id"] == "doc-1"
    assert fake.posts[0][1]["schema"]["vector"] == {"type": "[2]f32", "ann": True}
    assert fake.posts[1][1]["filters"] == ["tenant_id", "Eq", "acme"]
    assert fake.posts[1][1]["exclude_attributes"] == ["vector"]
    assert results[0]["id"] == "chunk-1"
    assert results[0]["score"] == pytest.approx(0.75)
    assert results[0]["metadata"] == {"tenant_id": "acme"}
    assert fake.posts[2][1] == {"delete_by_filter": ["document_id", "Eq", "doc-1"]}


def test_turbopuffer_adapter_handles_lifecycle_chunks_and_exports() -> None:
    asyncio.run(_test_turbopuffer_adapter_handles_lifecycle_chunks_and_exports())


async def _test_turbopuffer_adapter_handles_lifecycle_chunks_and_exports() -> None:
    store = TurbopufferVectorStore(api_key="tpuf", region="aws-us-east-1")
    fake = FakeTurbopufferClient()
    store.client = fake

    await store.health_check()
    await store.create_collection("docs", 2)
    chunks, total = await store.get_chunks("docs", "doc-1")
    await store.delete_by_ids("docs", ["chunk-1"])
    upserted = await store.upsert("docs", ["chunk-2"], [[0.3]], ["text"], [{"kind": "note"}])
    exported = await store.export_collection_points("docs")
    exported_without_vectors = await store.export_collection_points("docs", with_vectors=False)
    await store.delete_collection("docs")
    await store.close()

    assert fake.gets == ["/v1/namespaces"]
    assert fake.posts[0][1]["schema"]["vector"] == {"type": "[2]f32", "ann": True}
    assert fake.posts[0][1]["schema"]["bigrag_id"] == {"type": "string"}
    assert "upsert_rows" not in fake.posts[0][1]
    assert fake.posts[1][1]["exclude_attributes"] == ["vector"]
    assert chunks == [
        {
            "id": "chunk-1",
            "document_id": "doc-1",
            "text": "hello",
            "chunk_index": 0,
            "metadata": {"tenant_id": "acme"},
        }
    ]
    assert total == 1
    assert fake.posts[2][1]["deletes"] == [_point_id("bigrag_docs", "chunk-1")]
    assert upserted == 1
    assert exported == [
        {
            "id": "point-1",
            "payload": {
                "id": "chunk-1",
                "text": "hello",
                "document_id": "doc-1",
                "chunk_index": 0,
                "tenant_id": "acme",
            },
            "vector": None,
        }
    ]
    assert fake.posts[5][1]["exclude_attributes"] == ["vector"]
    assert "include_attributes" not in fake.posts[5][1]
    assert exported_without_vectors == [
        {
            "id": "point-1",
            "payload": {
                "id": "chunk-1",
                "text": "hello",
                "document_id": "doc-1",
                "chunk_index": 0,
                "tenant_id": "acme",
            },
            "vector": None,
        }
    ]
    assert fake.deletes == ["/v2/namespaces/bigrag_docs"]
    assert fake.closed is True


def test_turbopuffer_export_pages_by_primary_id(monkeypatch) -> None:
    asyncio.run(_test_turbopuffer_export_pages_by_primary_id(monkeypatch))


async def _test_turbopuffer_export_pages_by_primary_id(monkeypatch) -> None:
    monkeypatch.setattr(turbopuffer_module, "_EXPORT_PAGE_SIZE", 2)
    store = TurbopufferVectorStore(api_key="tpuf", region="aws-us-east-1")
    fake = FakeTurbopufferClient()
    fake.query_pages = [
        [
            {"id": "point-1", "bigrag_id": "chunk-1", "vector": [0.1]},
            {"id": "point-2", "bigrag_id": "chunk-2", "vector": [0.2]},
        ],
        [{"id": "point-3", "bigrag_id": "chunk-3", "vector": [0.3]}],
    ]
    store.client = fake

    exported = await store.export_collection_points("docs")

    assert exported == [
        {"id": "point-1", "payload": {"id": "chunk-1"}, "vector": [0.1]},
        {"id": "point-2", "payload": {"id": "chunk-2"}, "vector": [0.2]},
        {"id": "point-3", "payload": {"id": "chunk-3"}, "vector": [0.3]},
    ]
    assert "filters" not in fake.posts[0][1]
    assert fake.posts[1][1]["filters"] == ["id", "Gt", "point-2"]


def test_cloud_adapters_fail_keyword_search_clearly() -> None:
    asyncio.run(_test_cloud_adapters_fail_keyword_search_clearly())


async def _test_cloud_adapters_fail_keyword_search_clearly() -> None:
    turbo = TurbopufferVectorStore(api_key="tpuf", region="aws-us-east-1")

    with pytest.raises(VectorStoreFeatureError):
        await turbo.text_search("docs", ["hello"])
    with pytest.raises(RuntimeError, match="API key"):
        TurbopufferVectorStore(api_key=None, region="aws-us-east-1").connect()


class FakeVectorBackend:
    provider = "qdrant"
    supports_text_search = True

    def __init__(self) -> None:
        self.client = None
        self.calls = []

    def connect(self) -> None:
        self.calls.append(("connect",))
        self.client = "client"

    async def close(self) -> None:
        self.calls.append(("close",))
        self.client = None

    async def health_check(self) -> None:
        self.calls.append(("health_check",))

    async def create_collection(
        self,
        name,
        dimension,
        index_type="HNSW",
        tenant_field=None,
    ) -> None:
        self.calls.append(("create_collection", name, dimension, index_type, tenant_field))

    async def delete_collection(self, name) -> None:
        self.calls.append(("delete_collection", name))

    async def insert(
        self,
        collection,
        ids,
        document_ids,
        chunk_indices,
        texts,
        embeddings,
        metadata=None,
    ):
        self.calls.append(
            ("insert", collection, ids, document_ids, chunk_indices, texts, embeddings, metadata)
        )
        return len(ids)

    async def search(self, collection, query_embedding, top_k=10, filters=None):
        self.calls.append(("search", collection, query_embedding, top_k, filters))
        return [{"id": "chunk"}]

    async def get_chunks(self, collection, document_id, limit=10000, offset=0):
        self.calls.append(("get_chunks", collection, document_id, limit, offset))
        return ([{"id": "chunk"}], 1)

    async def delete_by_document(self, collection, document_id) -> None:
        self.calls.append(("delete_by_document", collection, document_id))

    async def delete_by_ids(self, collection, ids) -> None:
        self.calls.append(("delete_by_ids", collection, ids))

    async def text_search(self, collection, query_terms, top_k=10, filters=None):
        self.calls.append(("text_search", collection, query_terms, top_k, filters))
        return [{"id": "text"}]

    async def upsert(self, collection, ids, embeddings, texts, metadata=None):
        self.calls.append(("upsert", collection, ids, embeddings, texts, metadata))
        return len(ids)

    async def export_collection_points(self, collection, *, with_vectors=True):
        self.calls.append(("export_collection_points", collection, with_vectors))
        return [{"id": "point"}]


def test_vector_store_configures_providers_and_rejects_unknown() -> None:
    store = VectorStore()

    store.configure(qdrant_url="http://qdrant", search_ef=32)
    assert isinstance(store.backend, QdrantVectorStore)

    store.configure(
        provider="turbopuffer",
        turbopuffer_api_key="tpuf",
        turbopuffer_region="aws-eu-west-1",
        turbopuffer_namespace_prefix="ns_",
    )
    assert isinstance(store.backend, TurbopufferVectorStore)
    assert store.backend.region == "aws-eu-west-1"

    with pytest.raises(ValueError, match="Unsupported"):
        store.configure(provider="unknown")


def test_vector_store_delegates_backend_operations() -> None:
    asyncio.run(_test_vector_store_delegates_backend_operations())


async def _test_vector_store_delegates_backend_operations() -> None:
    store = VectorStore()
    backend = FakeVectorBackend()
    store.backend = backend

    assert store.supports_text_search is True
    assert store._client() == "client"
    assert store.client is None

    store.connect()
    await store.health_check()
    await store.create_collection("docs", 2, tenant_field="tenant_id")
    assert await store.insert("docs", ["id"], ["doc"], [0], ["text"], [[0.1]]) == 1
    assert await store.search("docs", [0.1]) == [{"id": "chunk"}]
    assert await store.get_chunks("docs", "doc") == ([{"id": "chunk"}], 1)
    await store.delete_by_document("docs", "doc")
    await store.delete_by_ids("docs", ["id"])
    assert await store.text_search("docs", ["text"]) == [{"id": "text"}]
    assert await store.upsert("docs", ["id"], [[0.1]], ["text"]) == 1
    assert await store.export_collection_points("docs") == [{"id": "point"}]
    await store.delete_collection("docs")
    await store.close()

    assert ("create_collection", "docs", 2, "HNSW", "tenant_id") in backend.calls
    assert ("delete_collection", "docs") in backend.calls
    assert store.client is None


class FakeQdrantPoint:
    def __init__(self, payload=None, score=0.75, id="point", vector=None) -> None:
        self.payload = payload or {}
        self.score = score
        self.id = id
        self.vector = vector


class FakeQdrantClient:
    def __init__(self) -> None:
        self.collections = set()
        self.created = []
        self.indexes = []
        self.upserts = []
        self.deletes = []
        self.scroll_pages = []
        self.query_calls = []
        self.closed = False

    async def close(self):
        self.closed = True

    async def get_collections(self):
        return {"collections": list(self.collections)}

    async def collection_exists(self, name):
        return name in self.collections

    async def create_collection(self, **kwargs):
        self.collections.add(kwargs["collection_name"])
        self.created.append(kwargs)

    async def delete_collection(self, name):
        self.collections.discard(name)
        self.deletes.append(("collection", name))

    async def create_payload_index(self, **kwargs):
        self.indexes.append(kwargs)

    async def upsert(self, **kwargs):
        self.upserts.append(kwargs)

    async def query_points(self, **kwargs):
        self.query_calls.append(kwargs)
        return type(
            "Result",
            (),
            {
                "points": [
                    FakeQdrantPoint(
                        payload={
                            "id": "chunk-1",
                            "document_id": "doc-1",
                            "chunk_index": 2,
                            "text": "hello",
                            "tenant_id": "acme",
                        },
                        score=0.9,
                    )
                ]
            },
        )()

    async def scroll(self, **kwargs):
        if self.scroll_pages:
            return self.scroll_pages.pop(0)
        return (
            [
                FakeQdrantPoint(
                    payload={
                        "id": "chunk-1",
                        "document_id": "doc-1",
                        "chunk_index": 0,
                        "text": "hello world",
                    },
                    vector=[0.1, 0.2],
                )
            ],
            None,
        )

    async def delete(self, **kwargs):
        self.deletes.append(("points", kwargs))


def test_qdrant_filter_translation_and_combination() -> None:
    expr = build_filter(
        {
            "tenant_id": "acme",
            "page_no": {"$gte": 2, "$lt": 9},
            "kind": {"$in": ["pdf", "docx"]},
            "archived": {"$ne": True},
        }
    )

    qfilter = _to_qdrant_filter(expr)

    assert qfilter is not None
    assert len(qfilter.must) == 4
    assert len(qfilter.must_not) == 1
    assert _to_qdrant_filter(None) is None
    assert QdrantVectorStore._combine_filters(None, None) is None
    assert QdrantVectorStore._combine_filters(qfilter) is qfilter
    assert QdrantVectorStore._combine_filters(qfilter, qfilter).must == [qfilter, qfilter]


def test_qdrant_adapter_collection_search_chunks_and_delete() -> None:
    asyncio.run(_test_qdrant_adapter_collection_search_chunks_and_delete())


async def _test_qdrant_adapter_collection_search_chunks_and_delete() -> None:
    client = FakeQdrantClient()
    store = QdrantVectorStore(prefix="test_", search_ef=64)
    store.client = client

    await store.health_check()
    await store.create_collection("docs", 2, tenant_field="tenant_id")
    inserted = await store.insert(
        "docs",
        ["chunk-1"],
        ["doc-1"],
        [2],
        ["hello"],
        [[0.1, 0.2]],
        [{"tenant_id": "acme"}],
    )
    results = await store.search("docs", [0.1, 0.2], filters=build_filter({"tenant_id": "acme"}))

    client.scroll_pages = [
        (
            [
                FakeQdrantPoint(payload={"id": "chunk-2", "chunk_index": 2, "text": "two"}),
                FakeQdrantPoint(payload={"id": "chunk-1", "chunk_index": 1, "text": "one"}),
            ],
            "next",
        ),
        ([], None),
    ]
    chunks, total = await store.get_chunks("docs", "doc-1", limit=1, offset=1)

    await store.delete_by_document("docs", "doc-1")
    await store.delete_by_ids("docs", ["chunk-1"])
    await store.delete_collection("docs")
    await store.close()

    assert inserted == 1
    assert client.created[0]["collection_name"] == "test_docs"
    assert {item["field_name"] for item in client.indexes} >= {"id", "text", "tenant_id"}
    assert client.upserts[0]["points"][0].payload["document_id"] == "doc-1"
    assert client.query_calls[0]["search_params"].hnsw_ef == 64
    assert results[0]["metadata"] == {"tenant_id": "acme"}
    assert chunks == [
        {"id": "chunk-2", "document_id": "", "text": "two", "chunk_index": 2, "metadata": {}}
    ]
    assert total == 2
    assert client.closed is True


def test_qdrant_text_search_upsert_export_and_error_paths() -> None:
    asyncio.run(_test_qdrant_text_search_upsert_export_and_error_paths())


async def _test_qdrant_text_search_upsert_export_and_error_paths() -> None:
    client = FakeQdrantClient()
    client.collections.add("bigrag_docs")
    store = QdrantVectorStore()
    store.client = client

    assert await store.text_search("docs", []) == []
    text_results = await store.text_search("docs", ["hello"], top_k=2)
    upserted = await store.upsert("docs", ["manual"], [[0.1, 0.2]], ["manual text"])

    client.scroll_pages = [
        ([FakeQdrantPoint(id="p1", payload={"id": "chunk-1"}, vector=[0.1])], "next"),
        ([FakeQdrantPoint(id="p2", payload={"id": "chunk-2"}, vector=[0.2])], None),
    ]
    exported = await store.export_collection_points("docs")

    class FailingClient(FakeQdrantClient):
        async def scroll(self, **kwargs):
            raise RuntimeError("query failed")

    failing = QdrantVectorStore()
    failing.client = FailingClient()
    assert await failing.text_search("docs", ["hello"]) == []

    missing = QdrantVectorStore()
    missing.client = FakeQdrantClient()
    assert await missing.get_chunks("docs", "doc-1") == ([], 0)
    assert await missing.export_collection_points("docs") == []
    await missing.delete_by_document("docs", "doc-1")

    assert text_results[0]["id"] == "chunk-1"
    assert upserted == 1
    assert exported == [
        {"id": "p1", "payload": {"id": "chunk-1"}, "vector": [0.1]},
        {"id": "p2", "payload": {"id": "chunk-2"}, "vector": [0.2]},
    ]


def test_qdrant_retry_reconnects_transient_errors() -> None:
    asyncio.run(_test_qdrant_retry_reconnects_transient_errors())


async def _test_qdrant_retry_reconnects_transient_errors() -> None:
    store = QdrantVectorStore()
    calls = 0
    reconnects = 0

    async def flaky():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("down")
        return "ok"

    async def reconnect():
        nonlocal reconnects
        reconnects += 1

    store.reconnect = reconnect

    assert await store._run_with_retry(flaky) == "ok"
    assert reconnects == 1
