from __future__ import annotations

import asyncio

import pytest

from bigrag.services._retrieval_filters import build_filter
from bigrag.services.vector_store import (
    QdrantVectorStore,
    S3VectorsStore,
    TurbopufferVectorStore,
    VectorStoreFeatureError,
    _to_s3_filter,
    _to_turbopuffer_filter,
)
from bigrag.services.vector_store.qdrant import _to_qdrant_filter


def test_s3_filter_translation() -> None:
    expr = build_filter(
        {
            "tenant_id": "acme",
            "page_no": {"$gte": 2, "$lt": 9},
            "kind": {"$in": ["pdf", "docx"]},
            "archived": {"$ne": True},
        }
    )

    assert _to_s3_filter(expr) == {
        "$and": [
            {"tenant_id": {"$eq": "acme"}},
            {"page_no": {"$gte": 2}},
            {"page_no": {"$lt": 9}},
            {"kind": {"$in": ["pdf", "docx"]}},
            {"archived": {"$ne": True}},
        ]
    }


def test_turbopuffer_filter_translation() -> None:
    expr = build_filter({"tenant_id": "acme", "page_no": {"$gt": 1}, "kind": {"$in": ["pdf"]}})

    assert _to_turbopuffer_filter(expr) == [
        "And",
        [
            ["tenant_id", "Eq", "acme"],
            ["page_no", "Gt", 1],
            ["kind", "In", ["pdf"]],
        ],
    ]


class FakeS3VectorsClient:
    def __init__(self) -> None:
        self.put_calls = []
        self.query_calls = []
        self.delete_calls = []

    def put_vectors(self, **kwargs):
        self.put_calls.append(kwargs)
        return {}

    def query_vectors(self, **kwargs):
        self.query_calls.append(kwargs)
        return {
            "vectors": [
                {
                    "key": "point-1",
                    "distance": 0.2,
                    "metadata": {
                        "id": "chunk-1",
                        "document_id": "doc-1",
                        "chunk_index": 3,
                        "text": "hello",
                        "tenant_id": "acme",
                    },
                }
            ]
        }

    def delete_vectors(self, **kwargs):
        self.delete_calls.append(kwargs)
        return {}


def test_s3_vectors_adapter_maps_upsert_query_and_delete() -> None:
    asyncio.run(_test_s3_vectors_adapter_maps_upsert_query_and_delete())


async def _test_s3_vectors_adapter_maps_upsert_query_and_delete() -> None:
    store = S3VectorsStore(bucket="bucket", region="us-east-1")
    fake = FakeS3VectorsClient()
    store.client = fake

    count = await store.insert(
        "docs",
        ["chunk-1"],
        ["doc-1"],
        [3],
        ["hello"],
        [[0.1, 0.2]],
        [{"tenant_id": "acme"}],
    )
    results = await store.search("docs", [0.1, 0.2], filters=build_filter({"tenant_id": "acme"}))
    await store.delete_by_ids("docs", ["chunk-1"])

    assert count == 1
    assert fake.put_calls[0]["indexName"] == "bigrag_docs"
    assert fake.put_calls[0]["vectors"][0]["metadata"]["document_id"] == "doc-1"
    assert fake.query_calls[0]["filter"] == {"tenant_id": {"$eq": "acme"}}
    assert results[0]["id"] == "chunk-1"
    assert results[0]["score"] == pytest.approx(0.8)
    assert fake.delete_calls[0]["indexName"] == "bigrag_docs"


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

    async def post(self, path: str, json: dict):
        self.posts.append((path, json))
        if path.endswith("/query"):
            return FakeResponse(
                {
                    "rows": [
                        {
                            "$dist": 0.25,
                            "id": "point-1",
                            "text": "hello",
                            "document_id": "doc-1",
                            "chunk_index": 0,
                        }
                    ]
                }
            )
        return FakeResponse()


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
    assert fake.posts[0][1]["upsert_rows"][0]["document_id"] == "doc-1"
    assert fake.posts[1][1]["filters"] == ["tenant_id", "Eq", "acme"]
    assert results[0]["score"] == pytest.approx(0.75)
    assert fake.posts[2][1] == {"delete_by_filter": ["document_id", "Eq", "doc-1"]}


def test_cloud_adapters_fail_keyword_search_clearly() -> None:
    asyncio.run(_test_cloud_adapters_fail_keyword_search_clearly())


async def _test_cloud_adapters_fail_keyword_search_clearly() -> None:
    store = S3VectorsStore(bucket="bucket", region="us-east-1")

    with pytest.raises(VectorStoreFeatureError):
        await store.text_search("docs", ["hello"])


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
    assert chunks == [{"id": "chunk-2", "text": "two", "chunk_index": 2}]
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
