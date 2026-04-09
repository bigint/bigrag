import httpx
from helpers import fail, ok


async def test_health(c: httpx.AsyncClient) -> None:
    print("\n── Health ──")

    r = await c.get("/health")
    if r.status_code == 200 and r.json()["status"] == "ok":
        ok("GET /health")
    else:
        fail("GET /health", f"{r.status_code}")

    r = await c.get("/health/ready")
    data = r.json()
    if data.get("postgres") and data.get("milvus") and data.get("redis"):
        ok("GET /health/ready")
    else:
        fail("GET /health/ready", f"services down: {data}")
