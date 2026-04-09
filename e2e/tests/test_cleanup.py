import httpx
from helpers import COLLECTION, fail, ok


async def test_cleanup(c: httpx.AsyncClient) -> None:
    print("\n── Cleanup ──")

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents",
        files={"file": ("del.txt", b"Delete me " * 10)},
    )
    if r.status_code == 201:
        del_id = r.json()["id"]
        r = await c.delete(f"/v1/collections/{COLLECTION}/documents/{del_id}")
        if r.status_code == 200:
            ok("Delete document")
        else:
            fail("Delete document", f"{r.status_code}")

    r = await c.delete(f"/v1/collections/{COLLECTION}")
    if r.status_code == 200:
        ok("Delete collection")
    else:
        fail("Delete collection", f"{r.status_code}")

    r = await c.get(f"/v1/collections/{COLLECTION}")
    if r.status_code == 404:
        ok("Collection → 404")
    else:
        fail("Collection 404", f"got {r.status_code}")
