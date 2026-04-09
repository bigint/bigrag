import httpx
from helpers import COLLECTION, OPENAI_KEY, fail, ok


async def test_collections(c: httpx.AsyncClient) -> None:
    print("\n── Collections ──")

    # Create
    r = await c.post("/v1/collections", json={
        "name": COLLECTION,
        "description": "E2E test",
        "chunk_size": 256,
        "chunk_overlap": 25,
        "embedding_api_key": OPENAI_KEY,
    })
    if r.status_code == 201:
        ok("Create")
    else:
        fail("Create", f"{r.status_code} {r.text}")
        raise SystemExit("Cannot continue without collection")

    # List
    r = await c.get("/v1/collections")
    names = [x["name"] for x in r.json()["collections"]]
    if COLLECTION in names:
        ok("List")
    else:
        fail("List", "not in list")

    # List with name filter
    r = await c.get(f"/v1/collections?name={COLLECTION}")
    if r.status_code == 200 and r.json()["total"] >= 1:
        ok("List (name filter)")
    else:
        fail("List (name filter)", f"{r.status_code}")

    # Get
    r = await c.get(f"/v1/collections/{COLLECTION}")
    if r.status_code == 200 and r.json()["name"] == COLLECTION:
        ok("Get")
    else:
        fail("Get", f"{r.status_code}")

    # Update
    r = await c.put(f"/v1/collections/{COLLECTION}", json={"description": "Updated"})
    if r.status_code == 200 and r.json()["description"] == "Updated":
        ok("Update")
    else:
        fail("Update", f"{r.status_code}")

    # Stats
    r = await c.get(f"/v1/collections/{COLLECTION}/stats")
    if r.status_code == 200:
        ok("Stats")
    else:
        fail("Stats", f"{r.status_code}")

    # Duplicate → 409
    r = await c.post("/v1/collections", json={
        "name": COLLECTION, "embedding_api_key": OPENAI_KEY,
    })
    if r.status_code == 409:
        ok("Duplicate → 409")
    else:
        fail("Duplicate", f"expected 409, got {r.status_code}")

    # 404
    r = await c.get("/v1/collections/nonexistent_xyz_99999")
    if r.status_code == 404:
        ok("Not found → 404")
    else:
        fail("Not found", f"expected 404, got {r.status_code}")
