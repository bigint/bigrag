import httpx
from helpers import COLLECTION, fail, ok


async def test_batch(c: httpx.AsyncClient) -> None:
    print("\n── Batch Operations ──")

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents/batch/upload",
        files=[
            ("files", ("b1.txt", b"Batch one " * 20)),
            ("files", ("b2.txt", b"Batch two " * 20)),
        ],
    )
    if r.status_code == 201 and len(r.json()["documents"]) == 2:
        ok("Batch upload")
        ids = [d["id"] for d in r.json()["documents"]]
    else:
        fail("Batch upload", f"{r.status_code}")
        return

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents/batch/status",
        json={"document_ids": ids},
    )
    if r.status_code == 200 and r.json()["total"] == 2:
        ok("Batch status")
    else:
        fail("Batch status", f"{r.status_code}")

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents/batch/get",
        json={"document_ids": ids},
    )
    if r.status_code == 200 and r.json()["total"] == 2:
        ok("Batch get")
    else:
        fail("Batch get", f"{r.status_code}")

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents/batch/delete",
        json={"document_ids": ids},
    )
    if r.status_code == 200 and r.json()["deleted"] == 2:
        ok("Batch delete")
    else:
        fail("Batch delete", f"{r.status_code}")
