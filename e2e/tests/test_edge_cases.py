import httpx
from helpers import COLLECTION, fail, ok


async def test_edge_cases(c: httpx.AsyncClient, doc_id: str | None) -> None:
    print("\n── Edge Cases ──")
    fake_uuid = "00000000-0000-0000-0000-000000000000"

    # --- Collection error paths ---

    r = await c.get("/v1/collections/nonexistent_xyz/stats")
    if r.status_code == 404:
        ok("Stats non-existent → 404")
    else:
        fail("Stats non-existent", f"expected 404, got {r.status_code}")

    r = await c.put("/v1/collections/nonexistent_xyz", json={"description": "x"})
    if r.status_code == 404:
        ok("Update non-existent → 404")
    else:
        fail("Update non-existent", f"expected 404, got {r.status_code}")

    r = await c.delete("/v1/collections/nonexistent_xyz")
    if r.status_code == 404:
        ok("Delete non-existent collection → 404")
    else:
        fail("Delete non-existent collection", f"expected 404, got {r.status_code}")

    r = await c.post("/v1/collections/nonexistent_xyz/truncate")
    if r.status_code == 404:
        ok("Truncate non-existent → 404")
    else:
        fail("Truncate non-existent", f"expected 404, got {r.status_code}")

    r = await c.post("/v1/collections", json={"name": ""})
    if r.status_code == 422:
        ok("Create empty name → 422")
    else:
        fail("Create empty name", f"expected 422, got {r.status_code}")

    # --- Document error paths ---

    if doc_id:
        r = await c.delete(f"/v1/collections/{COLLECTION}/documents/{doc_id}")
        if r.status_code == 200:
            ok("Delete single document")
        else:
            fail("Delete single document", f"{r.status_code}")

        r = await c.get(f"/v1/collections/{COLLECTION}/documents/{doc_id}")
        if r.status_code == 404:
            ok("Deleted document → 404")
        else:
            fail("Deleted document", f"expected 404, got {r.status_code}")

    r = await c.get(f"/v1/collections/{COLLECTION}/documents/{fake_uuid}")
    if r.status_code == 404:
        ok("Get non-existent document → 404")
    else:
        fail("Get non-existent document", f"expected 404, got {r.status_code}")

    r = await c.delete(f"/v1/collections/{COLLECTION}/documents/{fake_uuid}")
    if r.status_code == 404:
        ok("Delete non-existent document → 404")
    else:
        fail("Delete non-existent document", f"expected 404, got {r.status_code}")

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents/{fake_uuid}/reprocess"
    )
    if r.status_code == 404:
        ok("Reprocess non-existent → 404")
    else:
        fail("Reprocess non-existent", f"expected 404, got {r.status_code}")

    r = await c.get(f"/v1/collections/{COLLECTION}/documents/{fake_uuid}/chunks")
    if r.status_code == 404:
        ok("Chunks non-existent → 404")
    else:
        fail("Chunks non-existent", f"expected 404, got {r.status_code}")

    r = await c.get(f"/v1/collections/{COLLECTION}/documents/{fake_uuid}/file")
    if r.status_code == 404:
        ok("File non-existent → 404")
    else:
        fail("File non-existent", f"expected 404, got {r.status_code}")

    # --- Query error paths ---

    r = await c.post("/v1/collections/nonexistent_xyz/query", json={
        "query": "test", "top_k": 5,
    })
    if r.status_code == 404:
        ok("Query non-existent collection → 404")
    else:
        fail("Query non-existent", f"expected 404, got {r.status_code}")

    r = await c.post("/v1/query", json={
        "query": "test", "collections": ["nonexistent_xyz"], "top_k": 5,
    })
    if r.status_code == 404:
        ok("Multi-query non-existent → 404")
    else:
        fail("Multi-query non-existent", f"expected 404, got {r.status_code}")

    r = await c.get("/v1/collections/nonexistent_xyz/analytics")
    if r.status_code == 404:
        ok("Analytics non-existent → 404")
    else:
        fail("Analytics non-existent", f"expected 404, got {r.status_code}")

    # --- Batch error paths ---

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents/batch/status",
        json={"document_ids": [fake_uuid]},
    )
    if r.status_code == 200:
        ok("Batch status with non-existent IDs")
    else:
        fail("Batch status non-existent", f"{r.status_code}")

    r = await c.post(
        f"/v1/collections/{COLLECTION}/documents/batch/delete",
        json={"document_ids": [fake_uuid]},
    )
    if r.status_code == 200:
        ok("Batch delete non-existent IDs")
    else:
        fail("Batch delete non-existent", f"{r.status_code}")

    # --- Webhook error paths ---

    r = await c.get(f"/v1/admin/webhooks/{fake_uuid}")
    if r.status_code == 404:
        ok("Get non-existent webhook → 404")
    else:
        fail("Get non-existent webhook", f"expected 404, got {r.status_code}")

    r = await c.put(f"/v1/admin/webhooks/{fake_uuid}", json={"description": "test"})
    if r.status_code == 404:
        ok("Update non-existent webhook → 404")
    else:
        fail("Update non-existent webhook", f"expected 404, got {r.status_code}")

    r = await c.delete(f"/v1/admin/webhooks/{fake_uuid}")
    if r.status_code == 404:
        ok("Delete non-existent webhook → 404")
    else:
        fail("Delete non-existent webhook", f"expected 404, got {r.status_code}")

    # --- S3 job error paths ---

    r = await c.get(f"/v1/collections/{COLLECTION}/s3-jobs/{fake_uuid}")
    if r.status_code == 404:
        ok("Get non-existent S3 job → 404")
    else:
        fail("Get non-existent S3 job", f"expected 404, got {r.status_code}")

    r = await c.post(f"/v1/collections/{COLLECTION}/s3-jobs/{fake_uuid}/resync")
    if r.status_code == 404:
        ok("Resync non-existent S3 job → 404")
    else:
        fail("Resync non-existent S3 job", f"expected 404, got {r.status_code}")

    r = await c.delete(f"/v1/collections/{COLLECTION}/s3-jobs/{fake_uuid}")
    if r.status_code == 404:
        ok("Delete non-existent S3 job → 404")
    else:
        fail("Delete non-existent S3 job", f"expected 404, got {r.status_code}")
