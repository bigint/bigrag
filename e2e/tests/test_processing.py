import httpx
from helpers import COLLECTION, fail, ok, wait_doc


async def test_processing(c: httpx.AsyncClient) -> tuple[str | None, str | None]:
    """Upload docs, wait for processing, test chunks and file download."""
    print("\n── Processing ──")

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents",
        files={"file": ("proc.txt", b"Processing test content. " * 20)},
    )
    doc_id = r.json()["id"] if r.status_code == 201 else None

    r2 = await c.post(
        f"/v1/collections/{COLLECTION}/documents",
        files={"file": ("proc2.md", b"# Processing\n\nTest.\n" * 10)},
    )
    doc2_id = r2.json()["id"] if r2.status_code == 201 else None

    if doc_id:
        status = await wait_doc(c, doc_id)
        if status == "ready":
            ok("Document → ready")
        else:
            r = await c.get(f"/v1/collections/{COLLECTION}/documents/{doc_id}")
            fail("Document processing", f"status={status} err={r.json().get('error_message')}")

        if status == "ready":
            r = await c.get(f"/v1/collections/{COLLECTION}/documents/{doc_id}/chunks")
            if r.status_code == 200 and r.json()["total"] > 0:
                ok("Chunks (scoped)")
            else:
                fail("Chunks (scoped)", f"total={r.json().get('total')}")

            r = await c.get(f"/v1/documents/{doc_id}/chunks")
            if r.status_code == 200 and r.json()["total"] > 0:
                ok("Chunks (global)")
            else:
                fail("Chunks (global)", f"{r.status_code}")

        r = await c.get(f"/v1/collections/{COLLECTION}/documents/{doc_id}/file")
        if r.status_code == 200 and len(r.content) > 0:
            ok("File download")
        else:
            fail("File download", f"{r.status_code}")

        r = await c.post(f"/v1/collections/{COLLECTION}/documents/{doc_id}/reprocess")
        if r.status_code == 200:
            ok("Reprocess trigger")
        else:
            fail("Reprocess trigger", f"{r.status_code}")

        st = await wait_doc(c, doc_id)
        if st == "ready":
            ok("Reprocess → ready")
        else:
            fail("Reprocess", f"status={st}")

    return doc_id, doc2_id
