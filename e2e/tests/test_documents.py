import json

import httpx
from helpers import COLLECTION, fail, ok


async def test_documents(c: httpx.AsyncClient) -> tuple[str | None, str | None]:
    print("\n── Documents ──")

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents",
        files={"file": ("test.txt", b"Test document for E2E testing. " * 20)},
        data={"metadata": json.dumps({"source": "e2e"})},
    )
    doc_id = None
    if r.status_code == 201:
        ok("Upload txt")
        doc_id = r.json()["id"]
    else:
        fail("Upload txt", f"{r.status_code} {r.text}")

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents",
        files={"file": ("test.md", b"# Test\n\nMarkdown.\n" * 10)},
    )
    doc2_id = r.json()["id"] if r.status_code == 201 else None
    if r.status_code == 201:
        ok("Upload markdown")
    else:
        fail("Upload markdown", f"{r.status_code}")

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents",
        files={"file": ("bad.xyz", b"nope")},
    )
    if r.status_code == 400:
        ok("Reject unsupported type → 400")
    else:
        fail("Reject unsupported", f"expected 400, got {r.status_code}")

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents",
        files={"file": ("empty.txt", b"")},
    )
    if r.status_code == 400:
        ok("Reject empty → 400")
    else:
        fail("Reject empty", f"expected 400, got {r.status_code}")

    r = await c.get(f"/v1/collections/{COLLECTION}/documents")
    if r.status_code == 200 and r.json()["total"] >= 2:
        ok("List")
    else:
        fail("List", f"total={r.json().get('total')}")

    r = await c.get(f"/v1/collections/{COLLECTION}/documents?limit=1&offset=0")
    if r.status_code == 200 and len(r.json()["documents"]) == 1:
        ok("List (pagination)")
    else:
        fail("List (pagination)", f"{r.status_code}")

    r = await c.get(f"/v1/collections/{COLLECTION}/documents?status=pending")
    if r.status_code == 200:
        ok("List (status filter)")
    else:
        fail("List (status filter)", f"{r.status_code}")

    if doc_id:
        r = await c.get(f"/v1/collections/{COLLECTION}/documents/{doc_id}")
        if r.status_code == 200:
            ok("Get (scoped)")
        else:
            fail("Get (scoped)", f"{r.status_code}")

    if doc_id:
        r = await c.get(f"/v1/documents/{doc_id}")
        if r.status_code == 200:
            ok("Get (global)")
        else:
            fail("Get (global)", f"{r.status_code} {r.text}")

    r = await c.get(
        f"/v1/collections/{COLLECTION}/documents/00000000-0000-0000-0000-000000000000"
    )
    if r.status_code == 404:
        ok("Not found → 404")
    else:
        fail("Not found", f"got {r.status_code}")

    return doc_id, doc2_id
