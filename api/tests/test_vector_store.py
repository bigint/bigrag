from __future__ import annotations

import asyncio

import pytest

from bigrag.services._retrieval_filters import build_filter
from bigrag.services.vector_store import (
    S3VectorsStore,
    TurbopufferVectorStore,
    VectorStoreFeatureError,
    _to_s3_filter,
    _to_turbopuffer_filter,
)


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
