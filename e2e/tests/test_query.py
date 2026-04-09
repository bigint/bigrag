import httpx
from helpers import COLLECTION, fail, ok, wait_doc


async def test_query(c: httpx.AsyncClient, doc2_id: str | None) -> None:
    print("\n── Query ──")

    if doc2_id:
        await wait_doc(c, doc2_id)

    # Single collection
    r = await c.post(f"/v1/collections/{COLLECTION}/query", json={
        "query": "test document", "top_k": 5,
    })
    if r.status_code == 200 and "results" in r.json():
        ok("Query collection")
    else:
        fail("Query collection", f"{r.status_code} {r.text}")

    # Multi-collection
    r = await c.post("/v1/query", json={
        "query": "test", "collections": [COLLECTION], "top_k": 5,
    })
    if r.status_code == 200 and "results" in r.json():
        ok("Multi-collection query")
    else:
        fail("Multi-collection query", f"{r.status_code}")

    # Batch
    r = await c.post("/v1/batch/query", json={
        "queries": [{"collection": COLLECTION, "query": "test", "top_k": 3}],
    })
    if r.status_code == 200 and "results" in r.json():
        ok("Batch query")
    else:
        fail("Batch query", f"{r.status_code}")

    # Embeddings
    r = await c.get("/v1/embeddings/models")
    if r.status_code == 200 and len(r.json()["models"]) > 0:
        ok("List embedding models")
    else:
        fail("List embedding models", f"{r.status_code}")

    # Stats
    r = await c.get("/v1/stats")
    if r.status_code == 200 and "collections" in r.json():
        ok("Platform stats")
    else:
        fail("Platform stats", f"{r.status_code}")

    # Analytics
    r = await c.get(f"/v1/collections/{COLLECTION}/analytics")
    if r.status_code == 200:
        ok("Collection analytics")
    else:
        fail("Collection analytics", f"{r.status_code}")
