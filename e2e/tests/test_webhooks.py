import httpx
from helpers import fail, ok


async def test_webhooks(c: httpx.AsyncClient) -> None:
    print("\n── Webhooks ──")

    r = await c.post("/v1/admin/webhooks", json={
        "url": "https://httpbin.org/post",
        "events": ["document.ready"],
        "description": "E2E test",
    })
    if r.status_code == 201:
        ok("Create")
        wh_id = r.json()["id"]
    else:
        fail("Create", f"{r.status_code}")
        return

    r = await c.get("/v1/admin/webhooks")
    if r.status_code == 200:
        ok("List")
    else:
        fail("List", f"{r.status_code}")

    r = await c.get(f"/v1/admin/webhooks/{wh_id}")
    if r.status_code == 200:
        ok("Get")
    else:
        fail("Get", f"{r.status_code}")

    r = await c.put(f"/v1/admin/webhooks/{wh_id}", json={"description": "Updated"})
    if r.status_code == 200:
        ok("Update")
    else:
        fail("Update", f"{r.status_code}")

    r = await c.get(f"/v1/admin/webhooks/{wh_id}/deliveries")
    if r.status_code == 200 and "deliveries" in r.json():
        ok("List deliveries")
    else:
        fail("List deliveries", f"{r.status_code}")

    r = await c.post(f"/v1/admin/webhooks/{wh_id}/test")
    if r.status_code == 200:
        ok("Test webhook")
    else:
        fail("Test webhook", f"{r.status_code}")

    r = await c.delete(f"/v1/admin/webhooks/{wh_id}")
    if r.status_code == 200:
        ok("Delete")
    else:
        fail("Delete", f"{r.status_code}")
