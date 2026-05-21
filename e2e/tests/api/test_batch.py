"""End-to-end tests for the batch endpoints under bigrag.routers.documents.

Endpoints covered:
- POST /v1/collections/{name}/documents/batch/upload
- POST /v1/collections/{name}/documents/batch/status
- POST /v1/collections/{name}/documents/batch/get
- POST /v1/collections/{name}/documents/batch/delete

Behavioural coverage:
- Upload 3 files at once → all returned with deterministic shape.
- batch/status returns each requested document (skips unknown ids).
- batch/get returns each requested document.
- batch/delete removes all three from the collection.
- Dedup: uploading the same file twice in a batch yields one doc, with
  the duplicate flagged as ``deduped=true``.

Skipped (too slow / size-bound, would slow CI for marginal value):
- Exceeding the 100-file batch limit (asserted at API: HTTP 400).
- Exceeding the batch total-size budget (asserted at API: HTTP 413).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from tests._helpers import assert_envelope, read_fixture

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _three_files() -> list[tuple[str, tuple[str, bytes, str]]]:
    """Three distinct small text payloads as a list of multipart tuples."""
    return [
        ("files", ("a.txt", b"alpha content one", "text/plain")),
        ("files", ("b.txt", b"beta content two", "text/plain")),
        ("files", ("c.txt", b"gamma content three", "text/plain")),
    ]


# ---------------------------------------------------------------------------
# batch/upload
# ---------------------------------------------------------------------------


async def test_batch_upload_returns_three_documents(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/upload",
        files=_three_files(),
    )
    body = assert_envelope(resp, 201)
    assert body["total"] == 3
    assert len(body["documents"]) == 3
    ids = {d["id"] for d in body["documents"]}
    assert len(ids) == 3


async def test_batch_upload_dedup_flags_duplicates(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    content = read_fixture("sample.txt")
    files = [
        ("files", ("first.txt", content, "text/plain")),
        ("files", ("first.txt", content, "text/plain")),  # exact dup
    ]
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/upload",
        files=files,
    )
    body = assert_envelope(resp, 201)
    assert body["total"] == 2
    # First wins; second should reference the same id and be flagged.
    ids = [d["id"] for d in body["documents"]]
    assert ids[0] == ids[1]
    assert body["documents"][1]["deduped"] is True


async def test_batch_upload_unsupported_extension_returns_400(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    files = [
        ("files", ("ok.txt", b"hello", "text/plain")),
        ("files", ("bad.exe", b"\x4d\x5a", "application/octet-stream")),
    ]
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/upload",
        files=files,
    )
    assert resp.status_code == 400, resp.text


# ---------------------------------------------------------------------------
# batch/status
# ---------------------------------------------------------------------------


async def test_batch_status_returns_all_three(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    upload = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/upload",
        files=_three_files(),
    )
    upload_body = assert_envelope(upload, 201)
    ids = [d["id"] for d in upload_body["documents"]]

    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/status",
        json={"document_ids": ids},
    )
    body = assert_envelope(resp, 200)
    assert body["total"] == 3
    returned = {d["id"] for d in body["documents"]}
    assert returned == set(ids)
    for d in body["documents"]:
        assert d["status"] in {"pending", "processing", "ready", "failed"}


async def test_batch_status_skips_unknown_ids(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    upload = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/upload",
        files=_three_files(),
    )
    upload_body = assert_envelope(upload, 201)
    real_id = upload_body["documents"][0]["id"]

    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/status",
        json={
            "document_ids": [real_id, "00000000-0000-0000-0000-000000000000"],
        },
    )
    body = assert_envelope(resp, 200)
    assert body["total"] == 1
    assert body["documents"][0]["id"] == real_id


async def test_batch_status_invalid_uuid_returns_404(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/status",
        json={"document_ids": ["not-a-uuid"]},
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# batch/get
# ---------------------------------------------------------------------------


async def test_batch_get_returns_documents(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    upload = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/upload",
        files=_three_files(),
    )
    upload_body = assert_envelope(upload, 201)
    ids = [d["id"] for d in upload_body["documents"]]

    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/get",
        json={"document_ids": ids},
    )
    body = assert_envelope(resp, 200)
    assert body["total"] == 3
    returned = {d["id"] for d in body["documents"]}
    assert returned == set(ids)
    # Spot-check the per-doc shape we rely on:
    for d in body["documents"]:
        assert "filename" in d
        assert "status" in d
        assert "content_hash" in d


async def test_batch_get_unknown_ids_return_empty(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/get",
        json={"document_ids": ["00000000-0000-0000-0000-000000000000"]},
    )
    body = assert_envelope(resp, 200)
    assert body["total"] == 0
    assert body["documents"] == []


# ---------------------------------------------------------------------------
# batch/delete
# ---------------------------------------------------------------------------


async def test_batch_delete_removes_all_three(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    upload = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/upload",
        files=_three_files(),
    )
    upload_body = assert_envelope(upload, 201)
    ids = [d["id"] for d in upload_body["documents"]]

    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/delete",
        json={"document_ids": ids},
    )
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"
    assert body["deleted"] == 3
    assert body["errors"] == []

    # Confirm they're gone.
    follow_up = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/get",
        json={"document_ids": ids},
    )
    follow_body = assert_envelope(follow_up, 200)
    assert follow_body["total"] == 0


async def test_batch_delete_unknown_id_returns_error_entry(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/delete",
        json={"document_ids": ["00000000-0000-0000-0000-000000000000"]},
    )
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"
    assert body["deleted"] == 0
    assert len(body["errors"]) == 1
    assert body["errors"][0]["error"] == "Document not found"


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


async def test_batch_upload_requires_auth(
    unauth_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await unauth_client.post(
        f"/v1/collections/{coll['name']}/documents/batch/upload",
        files=_three_files(),
        headers={"Origin": "http://localhost:4000"},
    )
    assert resp.status_code == 401, resp.text


async def test_api_key_without_upload_scope_cannot_batch_upload(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    client = await api_key_client(scopes=["document:read"])
    resp = await client.post(
        f"/v1/collections/{coll['name']}/documents/batch/upload",
        files=_three_files(),
    )
    assert resp.status_code == 403, resp.text


async def test_api_key_without_delete_scope_cannot_batch_delete(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    client = await api_key_client(scopes=["document:read"])
    resp = await client.post(
        f"/v1/collections/{coll['name']}/documents/batch/delete",
        json={"document_ids": ["00000000-0000-0000-0000-000000000000"]},
    )
    assert resp.status_code == 403, resp.text
