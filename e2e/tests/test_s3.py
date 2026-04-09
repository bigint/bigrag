import asyncio

import httpx
from helpers import (
    COLLECTION,
    S3_ACCESS_KEY,
    S3_BUCKET,
    S3_ENDPOINT,
    S3_SECRET_KEY,
    fail,
    ok,
    skip,
)


async def test_s3(c: httpx.AsyncClient) -> None:
    print("\n── S3 Ingestion ──")

    if not S3_BUCKET:
        skip("E2E_S3_* env vars not set")
        return

    r = await c.post(f"/v1/collections/{COLLECTION}/documents/s3", json={
        "bucket": S3_BUCKET,
        "endpoint_url": S3_ENDPOINT or None,
        "access_key": S3_ACCESS_KEY or None,
        "secret_key": S3_SECRET_KEY or None,
        "region": "auto",
    })
    if r.status_code == 202:
        ok("Ingest")
    else:
        fail("Ingest", f"{r.status_code} {r.text}")

    r = await c.post(f"/v1/collections/{COLLECTION}/documents/s3", json={
        "bucket": S3_BUCKET,
        "endpoint_url": S3_ENDPOINT or None,
        "access_key": S3_ACCESS_KEY or None,
        "secret_key": S3_SECRET_KEY or None,
        "region": "auto",
        "file_types": ["pdf"],
    })
    if r.status_code == 202:
        ok("Ingest (file_types filter)")
    else:
        fail("Ingest (file_types)", f"{r.status_code}")

    await asyncio.sleep(2)

    r = await c.get(f"/v1/collections/{COLLECTION}/s3-jobs")
    if r.status_code == 200 and "jobs" in r.json():
        ok("List jobs")
        jobs = r.json()["jobs"]
        job_id = jobs[0]["id"] if jobs else None
    else:
        fail("List jobs", f"{r.status_code}")
        return

    if not job_id:
        fail("No jobs found", "empty list")
        return

    r = await c.get(f"/v1/collections/{COLLECTION}/s3-jobs/{job_id}")
    if r.status_code == 200:
        ok("Get job")
    else:
        fail("Get job", f"{r.status_code}")

    for _ in range(30):
        r = await c.get(f"/v1/collections/{COLLECTION}/s3-jobs/{job_id}")
        jst = r.json()["status"]
        if jst in ("complete", "failed"):
            break
        await asyncio.sleep(2)
    ok(f"Job finished (status={jst})")

    r = await c.post(f"/v1/collections/{COLLECTION}/s3-jobs/{job_id}/resync")
    if r.status_code == 200:
        ok("Resync")
    else:
        fail("Resync", f"{r.status_code}")

    await asyncio.sleep(3)
    for _ in range(20):
        r = await c.get(f"/v1/collections/{COLLECTION}/s3-jobs/{job_id}")
        if r.json()["status"] in ("complete", "failed"):
            break
        await asyncio.sleep(2)

    r = await c.delete(f"/v1/collections/{COLLECTION}/s3-jobs/{job_id}")
    if r.status_code == 200:
        ok("Delete job")
    else:
        fail("Delete job", f"{r.status_code}")

    r = await c.get(f"/v1/collections/{COLLECTION}/s3-jobs/{job_id}")
    if r.status_code == 404:
        ok("Deleted → 404")
    else:
        fail("Deleted 404", f"got {r.status_code}")
