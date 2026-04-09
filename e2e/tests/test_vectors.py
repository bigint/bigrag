import httpx
from helpers import COLLECTION, fail, ok


async def test_vectors(c: httpx.AsyncClient) -> None:
    print("\n── Vectors ──")

    r = await c.post(f"/v1/collections/{COLLECTION}/vectors/upsert", json={
        "vectors": [{
            "id": "vec-e2e-1",
            "embedding": [0.1] * 1536,
            "text": "Vector test",
            "metadata": {"source": "e2e"},
        }],
    })
    if r.status_code == 200 and r.json().get("upserted", 0) >= 1:
        ok("Upsert")
    else:
        fail("Upsert", f"{r.status_code} {r.text}")

    r = await c.post(f"/v1/collections/{COLLECTION}/vectors/delete", json={
        "ids": ["vec-e2e-1"],
    })
    if r.status_code == 200:
        ok("Delete")
    else:
        fail("Delete", f"{r.status_code}")
