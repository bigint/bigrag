import httpx
from helpers import COLLECTION, S3_BUCKET, fail, ok


async def test_truncate(c: httpx.AsyncClient) -> None:
    print("\n── Truncate ──")

    r = await c.post(f"/v1/collections/{COLLECTION}/truncate")
    if r.status_code == 200:
        ok("Truncate")
    else:
        fail("Truncate", f"{r.status_code} {r.text}")

    r = await c.get(f"/v1/collections/{COLLECTION}/documents")
    if r.status_code == 200 and r.json()["total"] == 0:
        ok("Documents cleared")
    else:
        fail("Documents cleared", f"total={r.json().get('total')}")

    r = await c.get(f"/v1/collections/{COLLECTION}")
    if r.status_code == 200:
        ok("Collection preserved")
    else:
        fail("Collection preserved", f"{r.status_code}")

    if S3_BUCKET:
        r = await c.get(f"/v1/collections/{COLLECTION}/s3-jobs")
        if r.status_code == 200 and r.json()["total"] > 0:
            ok("S3 jobs preserved")
        else:
            fail("S3 jobs preserved", f"total={r.json().get('total', 0)}")
