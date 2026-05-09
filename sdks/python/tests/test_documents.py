from __future__ import annotations

import asyncio

import httpx

from bigrag import BigRAG


def run(coro):
    return asyncio.run(coro)


def test_documents_resource_encodes_paths_and_query_params() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"documents": [], "total": 0}, request=request)

    async def scenario() -> dict:
        client = BigRAG(
            base_url="http://api.local",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            return await client.documents.list("team docs", status="ready", limit=5, offset=10)
        finally:
            await client.aclose()

    assert run(scenario()) == {"documents": [], "total": 0}
    assert str(seen[0].url) == (
        "http://api.local/v1/collections/team%20docs/documents?status=ready&limit=5&offset=10"
    )


def test_documents_upload_sends_metadata_and_file() -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = await request.aread()
        assert b'name="metadata"' in body
        assert b'{"tenant": "acme"}' in body
        assert b'name="file"; filename="note.txt"' in body
        return httpx.Response(
            201,
            json={
                "id": "doc",
                "collection_id": "col",
                "filename": "note.txt",
                "file_type": "txt",
                "file_size": 5,
                "chunk_count": 0,
                "status": "pending",
                "error_message": None,
                "metadata": {"tenant": "acme"},
                "content_hash": None,
                "deduped": False,
                "progress": None,
                "created_at": "2026-05-09T00:00:00Z",
                "updated_at": "2026-05-09T00:00:00Z",
            },
            request=request,
        )

    async def scenario() -> dict:
        client = BigRAG(
            base_url="http://api.local",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
        try:
            return await client.documents.upload(
                "docs",
                ("note.txt", b"hello"),
                metadata={"tenant": "acme"},
            )
        finally:
            await client.aclose()

    assert run(scenario())["filename"] == "note.txt"
    assert str(seen[0].url) == "http://api.local/v1/collections/docs/documents"


def test_get_file_url_uses_encoded_path() -> None:
    client = BigRAG(base_url="http://api.local/")

    assert client.documents.get_file_url("team docs", "doc/1") == (
        "http://api.local/v1/collections/team%20docs/documents/doc%2F1/file"
    )
