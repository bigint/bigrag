import httpx
from helpers import COLLECTION, fail, ok, wait_doc


async def test_sse(c: httpx.AsyncClient) -> None:
    print("\n── SSE Progress ──")

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents",
        files={"file": ("sse.txt", b"SSE progress test " * 10)},
    )
    if r.status_code != 201:
        fail("SSE upload", f"{r.status_code}")
        return

    doc_id = r.json()["id"]

    async with c.stream(
        "GET", f"/v1/collections/{COLLECTION}/documents/{doc_id}/progress",
    ) as resp:
        if resp.status_code == 200:
            ok("Document progress (connected)")
        else:
            fail("Document progress", f"{resp.status_code}")

    async with c.stream(
        "GET", f"/v1/collections/{COLLECTION}/documents/batch/progress?ids={doc_id}",
    ) as resp:
        if resp.status_code == 200:
            ok("Batch progress (connected)")
        else:
            fail("Batch progress", f"{resp.status_code}")

    await wait_doc(c, doc_id)
