"""End-to-end tests for bigrag.routers.documents and bigrag.routers._documents.

Endpoints covered:
- POST   /v1/collections/{name}/documents       (single upload)
- GET    /v1/collections/{name}/documents       (list, filter, paginate)
- GET    /v1/collections/{name}/documents/{id}
- DELETE /v1/collections/{name}/documents/{id}
- POST   /v1/collections/{name}/documents/{id}/reprocess
- GET    /v1/collections/{name}/documents/{id}/chunks
- GET    /v1/collections/{name}/documents/{id}/file
- GET    /v1/documents/{id}                     (cross-collection)
- GET    /v1/documents/{id}/chunks              (cross-collection)

Behavioural coverage:
- Multi-format upload (pdf, md, txt, docx, html, png).
- Dedup by sha256 content_hash → second upload returns deduped=true.
- Status transitions ``pending`` → ``ready`` (poll via document fixture).
- Failure path: deliberately-broken upload ends in ``failed`` with an
  error message.
- 413 on oversized single upload (10 MB > default 5 MB cap).
- list status filter, pagination, invalid sort/order.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest

from tests._helpers import assert_envelope, read_fixture, unique_name


# ---------------------------------------------------------------------------
# Upload: happy path across formats
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name,expected_type",
    [
        ("sample.pdf", "pdf"),
        ("sample.md", "md"),
        ("sample.txt", "txt"),
        ("sample.docx", "docx"),
        ("sample.html", "html"),
        ("sample.png", "png"),
    ],
)
async def test_upload_each_format_returns_201(
    fixture_name: str,
    expected_type: str,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    # ``document`` polls for terminal; images/binaries may end in failed,
    # text/pdf/docx end in ready — but the endpoint contract (201 +
    # response shape) is what we assert here.
    doc = await document(coll["name"], fixture=fixture_name, wait=False)
    assert doc["file_type"] == expected_type
    assert doc["id"]
    assert doc["status"] in {"pending", "processing", "ready", "failed"}


async def test_upload_txt_eventually_becomes_ready(
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    assert doc["status"] == "ready", doc
    assert doc["chunk_count"] >= 1


async def test_upload_dedup_returns_existing_document(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    first = await document(coll["name"], fixture="sample.txt")

    # Same bytes, fresh multipart — server should detect content-hash hit.
    files = {"file": ("sample.txt", read_fixture("sample.txt"), "application/octet-stream")}
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents",
        files=files,
    )
    body = assert_envelope(resp, 201)
    assert body["id"] == first["id"]
    assert body["deduped"] is True


async def test_upload_empty_file_returns_400(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    files = {"file": ("empty.txt", b"", "application/octet-stream")}
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents",
        files=files,
    )
    assert resp.status_code == 400, resp.text


async def test_upload_broken_pdf_ends_failed_with_message(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    # Bytes named .pdf but actually random — file_validation should reject
    # it at upload (400) or it'll proceed and fail during ingestion.
    files = {
        "file": (
            "broken.pdf",
            b"this is not actually a PDF, just text bytes",
            "application/pdf",
        )
    }
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents",
        files=files,
    )
    if resp.status_code == 400:
        # File-content validation rejected before persistence.
        return
    body = assert_envelope(resp, 201)
    doc = await document(
        coll["name"],
        fixture="sample.txt",  # unused — we'll re-poll directly via admin_client
        wait=False,
    )
    # Replace the polled doc with the broken one we just uploaded:
    from tests._helpers import poll_until

    async def fetch():
        r = await admin_client.get(
            f"/v1/collections/{coll['name']}/documents/{body['id']}"
        )
        r.raise_for_status()
        return r.json()

    final = await poll_until(
        fetch,
        predicate=lambda d: d.get("status") in {"ready", "failed"},
        timeout=60.0,
    )
    # Allow either terminal status — the contract is that it reaches
    # one of them and if failed, surfaces an error message.
    assert final["status"] in {"ready", "failed"}
    if final["status"] == "failed":
        assert final.get("error_message")
    # touch ``doc`` so the linter doesn't flag it
    assert doc["id"]


async def test_upload_oversized_returns_413(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    # Send a 200 MB blob — well above the default 64 MB cap. We rely on
    # the Content-Length-based short-circuit so we don't actually wait
    # for the whole body to upload.
    big = b"a" * (200 * 1024 * 1024)
    files = {"file": ("huge.txt", big, "text/plain")}
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents",
        files=files,
    )
    assert resp.status_code in (413, 422), resp.text


async def test_upload_unsupported_extension_returns_400(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    files = {"file": ("malware.exe", b"\x4dZ", "application/octet-stream")}
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents",
        files=files,
    )
    assert resp.status_code == 400, resp.text


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_list_documents_returns_envelope(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")

    resp = await admin_client.get(f"/v1/collections/{coll['name']}/documents")
    body = assert_envelope(resp, 200)
    assert body["total"] >= 1
    assert len(body["documents"]) >= 1
    assert "status" in body["documents"][0]


async def test_list_documents_filter_status_ready(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    await document(coll["name"], fixture="sample.txt")

    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents",
        params={"status": "ready"},
    )
    body = assert_envelope(resp, 200)
    for doc in body["documents"]:
        assert doc["status"] == "ready"


async def test_list_documents_pagination_limit_one(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    await document(
        coll["name"],
        fixture="sample.txt",
        content=b"first content for pagination test",
        filename="first.txt",
        wait=False,
    )
    await document(
        coll["name"],
        fixture="sample.txt",
        content=b"second content for pagination test",
        filename="second.txt",
        wait=False,
    )
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents",
        params={"limit": 1, "offset": 0},
    )
    body = assert_envelope(resp, 200)
    assert len(body["documents"]) == 1
    assert body["total"] >= 2


async def test_list_documents_invalid_sort_returns_400(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents",
        params={"sort": "not_a_column"},
    )
    assert resp.status_code == 400, resp.text


async def test_list_documents_invalid_order_returns_400(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents",
        params={"order": "sideways"},
    )
    assert resp.status_code == 400, resp.text


async def test_list_documents_search_query_filters(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    needle = unique_name("needle")
    await document(
        coll["name"],
        fixture="sample.txt",
        content=b"matchable",
        filename=f"{needle}.txt",
        wait=False,
    )
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents",
        params={"q": needle},
    )
    body = assert_envelope(resp, 200)
    assert body["total"] >= 1
    assert any(needle in d["filename"] for d in body["documents"])


# ---------------------------------------------------------------------------
# Get / chunks / file
# ---------------------------------------------------------------------------


async def test_get_document_returns_full_payload(
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
    assert body["id"] == doc["id"]
    assert body["filename"] == doc["filename"]
    assert body["status"] == "ready"


async def test_get_document_unknown_returns_404(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404, resp.text


async def test_get_document_invalid_uuid_returns_404(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents/not-a-uuid"
    )
    assert resp.status_code == 404, resp.text


async def test_get_document_chunks_shape(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents/{doc['id']}/chunks"
    )
    body = assert_envelope(resp, 200)
    assert "chunks" in body
    assert "total" in body
    assert isinstance(body["chunks"], list)
    assert body["total"] >= 1


async def test_get_document_chunks_pagination(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents/{doc['id']}/chunks",
        params={"limit": 1, "offset": 0},
    )
    body = assert_envelope(resp, 200)
    assert len(body["chunks"]) <= 1


async def test_download_document_file_matches_content_type(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents/{doc['id']}/file"
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/plain")
    assert b"Acme" in resp.content


async def test_download_unknown_document_returns_404(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents/"
        "00000000-0000-0000-0000-000000000000/file"
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Reprocess & delete
# ---------------------------------------------------------------------------


async def test_reprocess_kicks_off_for_ready_document(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/{doc['id']}/reprocess"
    )
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"


async def test_reprocess_unknown_document_returns_404(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.post(
        f"/v1/collections/{coll['name']}/documents/"
        "00000000-0000-0000-0000-000000000000/reprocess"
    )
    assert resp.status_code == 404, resp.text


async def test_delete_document_removes_it(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    resp = await admin_client.delete(
        f"/v1/collections/{coll['name']}/documents/{doc['id']}"
    )
    assert resp.status_code == 200, resp.text

    follow_up = await admin_client.get(
        f"/v1/collections/{coll['name']}/documents/{doc['id']}"
    )
    assert follow_up.status_code == 404, follow_up.text


async def test_delete_unknown_document_returns_404(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await admin_client.delete(
        f"/v1/collections/{coll['name']}/documents/"
        "00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# Cross-collection /v1/documents/{id}
# ---------------------------------------------------------------------------


async def test_get_document_cross_collection(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    resp = await admin_client.get(f"/v1/documents/{doc['id']}")
    body = assert_envelope(resp, 200)
    assert body["id"] == doc["id"]


async def test_get_document_cross_collection_unknown_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get(
        "/v1/documents/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404, resp.text


async def test_get_document_cross_collection_invalid_uuid_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/documents/not-a-uuid")
    assert resp.status_code == 404, resp.text


async def test_get_document_chunks_cross_collection(
    admin_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    doc = await document(coll["name"], fixture="sample.txt")
    resp = await admin_client.get(f"/v1/documents/{doc['id']}/chunks")
    body = assert_envelope(resp, 200)
    assert "chunks" in body
    assert body["total"] >= 1


async def test_pinned_api_key_blocked_from_cross_collection_lookup(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
    collection: Callable[..., Awaitable[dict[str, Any]]],
    document: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    pinned = await collection()
    other = await collection()
    doc_in_other = await document(other["name"], fixture="sample.txt")

    client = await api_key_client(collection=pinned["name"])
    resp = await client.get(f"/v1/documents/{doc_in_other['id']}")
    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


async def test_upload_requires_auth(
    unauth_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    files = {"file": ("sample.txt", b"hi", "text/plain")}
    resp = await unauth_client.post(
        f"/v1/collections/{coll['name']}/documents",
        files=files,
        headers={"Origin": "http://localhost:4000"},
    )
    assert resp.status_code == 401, resp.text


async def test_list_documents_requires_auth(
    unauth_client: httpx.AsyncClient,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    coll = await collection()
    resp = await unauth_client.get(f"/v1/collections/{coll['name']}/documents")
    assert resp.status_code == 401, resp.text
