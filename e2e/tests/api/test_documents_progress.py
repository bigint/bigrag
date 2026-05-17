"""End-to-end tests for bigrag.routers.documents_progress.

This module does *not* expose any HTTP endpoints — it's a small helpers
module that supplies the ``progress`` field embedded in every Document
response (``DocumentProgressResponse``). The helpers are imported by:

- ``routers/documents.py``  → ``GET/POST .../documents``, ``GET .../{id}``,
  ``GET .../documents/{id}/chunks``, batch/get & batch/status, the cross-
  collection ``/v1/documents/{id}``.
- ``routers/upload_sessions.py``  → file-add response.

These tests therefore cover the externally-observable behaviour of every
helper in ``documents_progress.py``:

- ``fallback_progress``: a freshly-uploaded doc that's already ``ready``
  exposes step=complete, status=complete, progress=1.0 (with chunk count
  in ``detail``) — see ``test_progress_on_ready_doc_is_complete`` and
  ``test_batch_status_progress_on_ready_doc_is_complete``.
- ``document_progress`` (single): a per-document GET surfaces the latest
  event-bus state, falling back to ``fallback_progress`` when no event is
  cached — see ``test_get_document_includes_progress_field``.
- ``document_progress_map`` (bulk): list/batch endpoints attach progress
  to every doc — see ``test_list_documents_each_has_progress``.
- ``publish_queued_progress``: the upload route publishes a ``queued``
  event before the worker picks the doc up — observable indirectly
  through the progress payload on the response.

There are no @router decorators in documents_progress.py; this file does
not need to assert HTTP status codes for that router, only that the
``progress`` payload contract is satisfied by every wired caller.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from tests._helpers import assert_envelope


PROGRESS_KEYS = {
    "document_id",
    "collection_name",
    "step",
    "status",
    "message",
    "progress",
    "detail",
}


def _assert_progress_shape(progress: dict[str, Any], *, doc_id: str) -> None:
    assert progress is not None, "progress must be present on Document responses"
    assert PROGRESS_KEYS.issubset(progress.keys()), progress
    assert progress["document_id"] == doc_id
    assert 0.0 <= progress["progress"] <= 1.0
    assert isinstance(progress["detail"], dict)


# ---------------------------------------------------------------------------
# document_progress / fallback_progress: terminal "ready"
# ---------------------------------------------------------------------------


async def test_progress_on_ready_doc_is_complete(
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    progress = doc.get("progress")
    _assert_progress_shape(progress, doc_id=doc["id"])
    assert progress["status"] in {"complete", "pending", "processing"}
    if doc["status"] == "ready":
        assert progress["status"] == "complete"
        assert progress["step"] == "complete"
        assert progress["progress"] == 1.0
        assert progress["detail"].get("chunks") == doc["chunk_count"]


async def test_get_document_includes_progress_field(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents/{doc['id']}"
    )
    body = assert_envelope(resp, 200)
    _assert_progress_shape(body["progress"], doc_id=doc["id"])


async def test_cross_collection_get_includes_progress_field(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    resp = await admin_client.get(f"/v1/documents/{doc['id']}")
    body = assert_envelope(resp, 200)
    _assert_progress_shape(body["progress"], doc_id=doc["id"])


# ---------------------------------------------------------------------------
# document_progress_map: list + batch endpoints
# ---------------------------------------------------------------------------


async def test_list_documents_each_has_progress(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    resp = await admin_client.get(f"/v1/collections/{coll['name']}/documents")
    body = assert_envelope(resp, 200)
    assert body["total"] >= 1
    for d in body["documents"]:
        _assert_progress_shape(d["progress"], doc_id=d["id"])
    listed = next(d for d in body["documents"] if d["id"] == doc["id"])
    if listed["status"] == "ready":
        assert listed["progress"]["status"] == "complete"


async def test_batch_status_progress_on_ready_doc_is_complete(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/status",
        json={"document_ids": [doc["id"]]},
    )
    body = assert_envelope(resp, 200)
    assert body["total"] == 1
    item = body["documents"][0]
    _assert_progress_shape(item["progress"], doc_id=doc["id"])
    if item["status"] == "ready":
        assert item["progress"]["status"] == "complete"
        assert item["progress"]["progress"] == 1.0


async def test_batch_get_progress_field_present(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/get",
        json={"document_ids": [doc["id"]]},
    )
    body = assert_envelope(resp, 200)
    assert body["total"] == 1
    _assert_progress_shape(body["documents"][0]["progress"], doc_id=doc["id"])


# ---------------------------------------------------------------------------
# publish_queued_progress: fresh upload returns a defined progress payload
# even before ingestion completes.
# ---------------------------------------------------------------------------


async def test_fresh_upload_response_carries_progress(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    files = {"file": ("hello.txt", b"hello world", "text/plain")}
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents",
        files=files,
    )
    body = assert_envelope(resp, 201)
    _assert_progress_shape(body["progress"], doc_id=body["id"])
    # Right after upload the worker may or may not have advanced the
    # document, so accept any pre-terminal or terminal status — what we
    # care about here is that the payload is well-formed.
    assert body["progress"]["status"] in {
        "pending",
        "processing",
        "complete",
        "failed",
    }
