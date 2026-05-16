from __future__ import annotations

import asyncio

import httpx

from bigrag import BigRAG
from bigrag._client import CollectionClient


def run(coro):
    return asyncio.run(coro)


class FakeDocuments:
    def __init__(self) -> None:
        self.calls = []

    async def upload(self, collection, file, *, metadata=None):
        self.calls.append(("upload", collection, file, metadata))
        return {"id": "doc"}

    async def list(self, collection, *, status=None, limit=None, offset=None):
        self.calls.append(("list", collection, status, limit, offset))
        return {"documents": [], "total": 0}

    async def get(self, collection, document_id):
        self.calls.append(("get", collection, document_id))
        return {"id": document_id}

    async def delete(self, collection, document_id):
        self.calls.append(("delete", collection, document_id))
        return {"status": "deleted"}

    async def batch_upload(self, collection, files, *, metadata=None):
        self.calls.append(("batch_upload", collection, files, metadata))
        return {"documents": [], "total": 0}

    async def create_upload_session(
        self, collection, *, total_files, total_bytes, metadata=None
    ):
        self.calls.append(
            ("create_upload_session", collection, total_files, total_bytes, metadata)
        )
        return {"id": "session"}

    async def get_upload_session(self, collection, session_id):
        self.calls.append(("get_upload_session", collection, session_id))
        return {"id": session_id}

    async def upload_session_file(
        self,
        collection,
        session_id,
        file,
        *,
        client_item_id=None,
        filename=None,
    ):
        self.calls.append(
            (
                "upload_session_file",
                collection,
                session_id,
                file,
                client_item_id,
                filename,
            )
        )
        return {"id": "item"}

    async def complete_upload_session(self, collection, session_id):
        self.calls.append(("complete_upload_session", collection, session_id))
        return {"id": session_id}

    async def cancel_upload_session(self, collection, session_id):
        self.calls.append(("cancel_upload_session", collection, session_id))
        return {"status": "canceled"}

    async def batch_get_status(self, collection, document_ids):
        self.calls.append(("batch_get_status", collection, document_ids))
        return {"documents": [], "total": 0}

    async def batch_get(self, collection, document_ids):
        self.calls.append(("batch_get", collection, document_ids))
        return {"documents": [], "total": 0}

    async def batch_delete(self, collection, document_ids):
        self.calls.append(("batch_delete", collection, document_ids))
        return {"status": "deleted", "deleted": len(document_ids)}

    async def reprocess(self, collection, document_id):
        self.calls.append(("reprocess", collection, document_id))
        return {"status": "queued"}

    async def get_chunks(self, collection, document_id, *, limit=None, offset=None):
        self.calls.append(("get_chunks", collection, document_id, limit, offset))
        return {"chunks": [], "total": 0}


class FakeCollections:
    def __init__(self) -> None:
        self.calls = []

    async def stats(self, collection):
        self.calls.append(("stats", collection))
        return {"document_count": 1}

    async def reembed(self, collection):
        self.calls.append(("reembed", collection))
        return {"status": "queued"}

    async def stream_events(self, collection):
        self.calls.append(("stream_events", collection))
        yield {"event": "progress"}


class FakeQueries:
    def __init__(self) -> None:
        self.calls = []

    async def query(self, collection, body):
        self.calls.append(("query", collection, body))
        return {"results": []}


class FakeBigRAG:
    def __init__(self) -> None:
        self.documents = FakeDocuments()
        self.collections = FakeCollections()
        self.queries = FakeQueries()
        self.analytics_calls = []

    async def get_analytics(self, collection):
        self.analytics_calls.append(collection)
        return {"collection": collection}


class FakeChat:
    async def create(self, body):
        return {"body": body}

    async def stream(self, body):
        yield {"event": "delta", "data": body}


def test_collection_client_delegates_to_scoped_resources() -> None:
    async def scenario():
        client = FakeBigRAG()
        collection = CollectionClient(client, "team docs")
        await collection.upload(b"hello", metadata={"tenant": "acme"})
        await collection.list_documents(status="ready", limit=5, offset=10)
        await collection.get_document("doc/1")
        await collection.delete_document("doc/1")
        await collection.batch_upload([b"one"], metadata={"batch": True})
        await collection.create_upload_session(total_files=1, total_bytes=3)
        await collection.get_upload_session("session/1")
        await collection.upload_session_file(
            "session/1",
            b"two",
            client_item_id="item-1",
            filename="two.txt",
        )
        await collection.complete_upload_session("session/1")
        await collection.cancel_upload_session("session/1")
        await collection.batch_get_status(["doc/1"])
        await collection.batch_get_documents(["doc/1"])
        await collection.stats()
        await collection.reembed()
        await collection.batch_delete(["doc/1", "doc/2"])
        await collection.reprocess_document("doc/1")
        await collection.get_document_chunks("doc/1", limit=2, offset=4)
        await collection.query({"query": "hello"})
        await collection.analytics()
        events = []
        async for event in collection.stream_events():
            events.append(event)
        return client, events

    client, events = run(scenario())

    assert client.documents.calls == [
        ("upload", "team docs", b"hello", {"tenant": "acme"}),
        ("list", "team docs", "ready", 5, 10),
        ("get", "team docs", "doc/1"),
        ("delete", "team docs", "doc/1"),
        ("batch_upload", "team docs", [b"one"], {"batch": True}),
        ("create_upload_session", "team docs", 1, 3, None),
        ("get_upload_session", "team docs", "session/1"),
        ("upload_session_file", "team docs", "session/1", b"two", "item-1", "two.txt"),
        ("complete_upload_session", "team docs", "session/1"),
        ("cancel_upload_session", "team docs", "session/1"),
        ("batch_get_status", "team docs", ["doc/1"]),
        ("batch_get", "team docs", ["doc/1"]),
        ("batch_delete", "team docs", ["doc/1", "doc/2"]),
        ("reprocess", "team docs", "doc/1"),
        ("get_chunks", "team docs", "doc/1", 2, 4),
    ]
    assert client.collections.calls == [
        ("stats", "team docs"),
        ("reembed", "team docs"),
        ("stream_events", "team docs"),
    ]
    assert client.queries.calls == [("query", "team docs", {"query": "hello"})]
    assert client.analytics_calls == ["team docs"]
    assert events == [{"event": "progress"}]


def test_bigrag_high_level_wrappers_delegate_to_resources() -> None:
    async def scenario():
        client = BigRAG(base_url="http://api.local")
        client.chat = FakeChat()
        created = await client.chat_create({"message": "hello", "collection": "docs"})
        streamed = []
        async for event in client.chat_stream({"message": "hello", "collection": "docs"}):
            streamed.append(event)
        scoped = client.collection("docs")
        await client.aclose()
        return created, streamed, scoped

    created, streamed, scoped = run(scenario())

    assert created == {"body": {"message": "hello", "collection": "docs"}}
    assert streamed == [{"event": "delta", "data": {"message": "hello", "collection": "docs"}}]
    assert isinstance(scoped, CollectionClient)
    assert scoped._name == "docs"


def test_bigrag_platform_methods_build_requests() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"status": "ok"}, request=request)

    async def scenario() -> list[dict]:
        client = BigRAG(
            base_url="http://api.local",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            return [
                await client.get_stats(),
                await client.list_embedding_models(),
                await client.get_analytics("team docs"),
            ]
        finally:
            await client.aclose()

    assert run(scenario()) == [{"status": "ok"}, {"status": "ok"}, {"status": "ok"}]
    assert [str(request.url) for request in seen] == [
        "http://api.local/v1/stats",
        "http://api.local/v1/embeddings/models",
        "http://api.local/v1/collections/team%20docs/analytics",
    ]
