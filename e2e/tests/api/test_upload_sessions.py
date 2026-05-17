"""End-to-end tests for bigrag.routers.upload_sessions.

Endpoints covered:
- POST   /v1/collections/{name}/upload-sessions
- GET    /v1/collections/{name}/upload-sessions/{session_id}
- POST   /v1/collections/{name}/upload-sessions/{session_id}/files
- POST   /v1/collections/{name}/upload-sessions/{session_id}/complete
- POST   /v1/collections/{name}/upload-sessions/{session_id}/cancel

Behavioural coverage:
- Full lifecycle: create → upload 2 files → complete → both documents
  end up in the target collection (polled to ``ready``).
- Cancel mid-flight: the session goes to ``canceled`` and adding files
  after cancel is rejected.
- Adding files after complete is rejected (409).
- Per-file failure modes: empty bytes and unsupported extensions are
  marked ``failed`` at item level (still HTTP 201).
- 404 for unknown session id.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from tests._helpers import assert_envelope, poll_until, unique_name


# ---------------------------------------------------------------------------
# Create / Get
# ---------------------------------------------------------------------------


async def test_create_upload_session_returns_201(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions",
        json={"total_files": 2, "total_bytes": 4096, "metadata": {}},
    )
    body = assert_envelope(resp, 201)
    assert body["id"]
    assert body["collection_name"] == coll["name"]
    assert body["total_files"] == 2
    assert body["uploaded_files"] == 0
    assert body["status"] in {"preparing", "ingesting", "complete"}


async def test_create_upload_session_zero_total_files_returns_422(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions",
        json={"total_files": 0, "total_bytes": 0},
    )
    assert resp.status_code == 422, resp.text


async def test_get_upload_session_returns_payload(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    create = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions",
        json={"total_files": 1, "total_bytes": 1024},
    )
    body = assert_envelope(create, 201)
    session_id = body["id"]

    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/upload-sessions/{session_id}"
    )
    got = assert_envelope(resp, 200)
    assert got["id"] == session_id
    assert got["total_files"] == 1


async def test_get_unknown_upload_session_returns_404(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/upload-sessions/"
        "00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404, resp.text


async def test_get_invalid_session_uuid_returns_404(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/upload-sessions/not-a-uuid"
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Full lifecycle
# ---------------------------------------------------------------------------


async def test_full_lifecycle_two_files_end_up_in_collection(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    file_a = b"upload session file A " + unique_name("a").encode()
    file_b = b"upload session file B " + unique_name("b").encode()
    create = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions",
        json={"total_files": 2, "total_bytes": len(file_a) + len(file_b)},
    )
    create_body = assert_envelope(create, 201)
    session_id = create_body["id"]

    resp_a = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions/{session_id}/files",
        files={"file": ("a.txt", file_a, "text/plain")},
        data={"client_item_id": "client-a"},
    )
    body_a = assert_envelope(resp_a, 201)
    assert body_a["item"]["client_item_id"] == "client-a"
    assert body_a["item"]["status"] in {"queued", "ingesting", "complete"}

    resp_b = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions/{session_id}/files",
        files={"file": ("b.txt", file_b, "text/plain")},
        data={"client_item_id": "client-b"},
    )
    body_b = assert_envelope(resp_b, 201)
    assert body_b["item"]["client_item_id"] == "client-b"

    complete = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions/{session_id}/complete"
    )
    complete_body = assert_envelope(complete, 200)
    assert complete_body["uploaded_files"] == 2

    async def fetch_session() -> dict[str, Any]:
        r = await admin_client.get(
            f"/v1/collections/{coll['name']}/upload-sessions/{session_id}"
        )
        r.raise_for_status()
        return r.json()

    final = await poll_until(
        fetch_session,
        predicate=lambda s: s["status"] in {"complete", "failed", "canceled"},
        timeout=60.0,
        description="upload session terminal status",
    )
    assert final["status"] == "complete"
    assert final["completed_files"] == 2

    # And the two documents now show up in the collection listing.
    docs = await admin_client.get(f"/v1/collections/{coll['name']}/documents")
    docs_body = assert_envelope(docs, 200)
    filenames = {d["filename"] for d in docs_body["documents"]}
    assert "a.txt" in filenames
    assert "b.txt" in filenames


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


async def test_cancel_before_files_uploaded(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    create = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions",
        json={"total_files": 2, "total_bytes": 1024},
    )
    create_body = assert_envelope(create, 201)
    session_id = create_body["id"]

    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions/{session_id}/cancel"
    )
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"

    follow_up = await admin_client.get(
        f"/v1/collections/{coll['name']}/upload-sessions/{session_id}"
    )
    follow_body = assert_envelope(follow_up, 200)
    assert follow_body["status"] == "canceled"


async def test_adding_files_after_cancel_returns_409(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    create = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions",
        json={"total_files": 2, "total_bytes": 1024},
    )
    session_id = create.json()["id"]

    cancel = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions/{session_id}/cancel"
    )
    assert cancel.status_code == 200, cancel.text

    add = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions/{session_id}/files",
        files={"file": ("late.txt", b"too late", "text/plain")},
        data={"client_item_id": "late"},
    )
    assert add.status_code == 409, add.text


async def test_complete_after_cancel_returns_409(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    create = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions",
        json={"total_files": 1, "total_bytes": 1024},
    )
    session_id = create.json()["id"]

    cancel = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions/{session_id}/cancel"
    )
    assert cancel.status_code == 200, cancel.text

    complete = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions/{session_id}/complete"
    )
    assert complete.status_code == 409, complete.text


# ---------------------------------------------------------------------------
# Item-level failure paths (still HTTP 201, with status=failed on the item)
# ---------------------------------------------------------------------------


async def test_upload_empty_file_marks_item_failed(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    create = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions",
        json={"total_files": 2, "total_bytes": 1024},
    )
    session_id = create.json()["id"]

    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions/{session_id}/files",
        files={"file": ("empty.txt", b"", "text/plain")},
        data={"client_item_id": "empty"},
    )
    body = assert_envelope(resp, 201)
    assert body["item"]["status"] == "failed"
    assert body["item"]["error_message"]


async def test_upload_unsupported_extension_marks_item_failed(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    create = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions",
        json={"total_files": 2, "total_bytes": 1024},
    )
    session_id = create.json()["id"]

    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions/{session_id}/files",
        files={"file": ("malware.exe", b"\x4dZ", "application/octet-stream")},
        data={"client_item_id": "exe"},
    )
    body = assert_envelope(resp, 201)
    assert body["item"]["status"] == "failed"
    assert "Unsupported" in (body["item"]["error_message"] or "")


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


async def test_create_upload_session_requires_auth(
    unauth_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await unauth_client.post(
        f"/v1/collections/{coll['name']}/upload-sessions",
        json={"total_files": 1, "total_bytes": 0},
        headers={"Origin": "http://localhost:4000"},
    )
    assert resp.status_code == 401, resp.text
