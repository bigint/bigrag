"""SDK contract tests for ``bigrag.DocumentsResource``.

Touches every public method on the resource::

    upload, batch_upload, list, get, get_by_id, delete, reprocess,
    get_chunks, get_chunks_by_id, get_file_url, batch_get_status,
    batch_get, batch_delete, create_upload_session, get_upload_session,
    upload_session_file, complete_upload_session, cancel_upload_session

plus the :class:`bigrag.CollectionClient` wrapper aliases for the same
operations.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from bigrag import BigRAG, NotFoundError
from tests._helpers import poll_until, read_fixture, unique_name


async def _wait_ready(client: BigRAG, coll: str, doc_id: str) -> dict[str, Any]:
    async def _fetch() -> dict[str, Any]:
        return await client.documents.get(coll, doc_id)

    return await poll_until(
        _fetch,
        predicate=lambda d: d.get("status") in {"ready", "failed"},
        timeout=60.0,
        interval=0.5,
        description=f"document {doc_id} ready",
    )


async def test_documents_upload_and_get(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    payload = read_fixture("sample.txt")

    uploaded = await client.documents.upload(
        coll["name"],
        (f"{unique_name('doc')}.txt", payload),
        metadata={"source": "sdk-test"},
    )
    for key in (
        "id",
        "collection_id",
        "filename",
        "file_type",
        "file_size",
        "status",
        "metadata",
        "created_at",
        "updated_at",
    ):
        assert key in uploaded
    assert uploaded["metadata"].get("source") == "sdk-test"

    ready = await _wait_ready(client, coll["name"], uploaded["id"])
    assert ready["status"] == "ready"
    assert ready["chunk_count"] >= 1

    fetched = await client.documents.get(coll["name"], uploaded["id"])
    assert fetched["id"] == uploaded["id"]

    by_id = await client.documents.get_by_id(uploaded["id"])
    assert by_id["id"] == uploaded["id"]


async def test_documents_list_and_pagination(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")

    listing = await client.documents.list(
        coll["name"], limit=10, offset=0, include_total=True
    )
    assert listing["total"] >= 1
    ids = [d["id"] for d in listing["documents"]]
    assert doc["id"] in ids

    filtered = await client.documents.list(coll["name"], status="ready", limit=5)
    assert all(d["status"] == "ready" for d in filtered["documents"])


async def test_documents_delete_then_get_raises_not_found(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")

    status = await client.documents.delete(coll["name"], doc["id"])
    assert status["status"] == "ok"

    with pytest.raises(NotFoundError):
        await client.documents.get(coll["name"], doc["id"])


async def test_documents_get_chunks_and_chunks_by_id(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")

    chunks = await client.documents.get_chunks(coll["name"], doc["id"], limit=10)
    assert chunks["total"] >= 1
    assert len(chunks["chunks"]) >= 1
    first = chunks["chunks"][0]
    for key in ("id", "document_id", "chunk_index", "text", "metadata"):
        assert key in first

    chunks_by_id = await client.documents.get_chunks_by_id(doc["id"], limit=10)
    assert chunks_by_id["total"] >= 1


async def test_documents_batch_upload_status_get_delete(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    # bigRAG dedups by content hash, so the two files need distinct bodies.
    payload_a = read_fixture("sample.txt") + b"\n# batch-a\n"
    payload_b = read_fixture("sample.txt") + b"\n# batch-b\n"
    files = [
        (f"batch-a-{unique_name('x')}.txt", payload_a),
        (f"batch-b-{unique_name('x')}.txt", payload_b),
    ]
    batch = await client.documents.batch_upload(coll["name"], files)
    assert batch["total"] == 2
    doc_ids = [d["id"] for d in batch["documents"]]

    for doc_id in doc_ids:
        await _wait_ready(client, coll["name"], doc_id)

    status = await client.documents.batch_get_status(coll["name"], doc_ids)
    assert status["total"] == 2
    for entry in status["documents"]:
        assert entry["id"] in doc_ids
        assert entry["status"] in {"ready", "failed", "pending", "processing"}

    bulk = await client.documents.batch_get(coll["name"], doc_ids)
    assert bulk["total"] == 2

    delete_resp = await client.documents.batch_delete(coll["name"], doc_ids)
    assert delete_resp["status"] in {"ok", "partial"}
    assert delete_resp["deleted"] >= 1


async def test_documents_reprocess(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    resp = await client.documents.reprocess(coll["name"], doc["id"])
    assert resp["status"] == "ok"


async def test_documents_get_file_url_shape(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    api_base_url: str,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    url = client.documents.get_file_url(coll["name"], "doc_id_xyz")
    assert url.startswith(api_base_url)
    assert coll["name"] in url
    assert url.endswith("/file")


async def test_documents_unknown_raises_not_found(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    with pytest.raises(NotFoundError):
        await client.documents.get(coll["name"], "00000000-0000-0000-0000-000000000000")


async def test_upload_session_round_trip(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    payload = read_fixture("sample.txt")

    session = await client.documents.create_upload_session(
        coll["name"],
        total_files=1,
        total_bytes=len(payload),
        metadata={"origin": "sdk"},
    )
    assert session["status"] in {"preparing", "uploading", "ingesting", "complete"}
    assert session["total_files"] == 1
    session_id = session["id"]

    got = await client.documents.get_upload_session(coll["name"], session_id)
    assert got["id"] == session_id

    upload = await client.documents.upload_session_file(
        coll["name"],
        session_id,
        (f"session-{unique_name('s')}.txt", payload),
        client_item_id=unique_name("item"),
    )
    assert "item" in upload and "session" in upload
    assert upload["session"]["id"] == session_id

    completed = await client.documents.complete_upload_session(coll["name"], session_id)
    assert completed["id"] == session_id


async def test_upload_session_cancel(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    client = await sdk_client()
    coll = await collection()
    session = await client.documents.create_upload_session(
        coll["name"], total_files=1, total_bytes=1024
    )
    cancel = await client.documents.cancel_upload_session(coll["name"], session["id"])
    assert cancel["status"] == "ok"


async def test_collection_client_document_wrappers(
    sdk_client: Callable[..., Awaitable[BigRAG]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    """Exercise CollectionClient document aliases in one go to make sure
    each delegate hits the right resource path."""
    client = await sdk_client()
    coll = await collection()
    scoped = client.collection(coll["name"])

    payload = read_fixture("sample.txt")
    uploaded = await scoped.upload(
        (f"{unique_name('cc')}.txt", payload), metadata={"via": "wrapper"}
    )
    await _wait_ready(client, coll["name"], uploaded["id"])

    listed = await scoped.list_documents(limit=5)
    assert any(d["id"] == uploaded["id"] for d in listed["documents"])

    got = await scoped.get_document(uploaded["id"])
    assert got["id"] == uploaded["id"]

    chunks = await scoped.get_document_chunks(uploaded["id"], limit=5)
    assert chunks["total"] >= 1

    status = await scoped.batch_get_status([uploaded["id"]])
    assert status["total"] == 1

    bulk = await scoped.batch_get_documents([uploaded["id"]])
    assert bulk["total"] == 1

    reprocess = await scoped.reprocess_document(uploaded["id"])
    assert reprocess["status"] == "ok"
    # let any background work settle so deletion doesn't race
    await asyncio.sleep(0.05)

    delete_resp = await scoped.batch_delete([uploaded["id"]])
    assert delete_resp["status"] in {"ok", "partial"}
