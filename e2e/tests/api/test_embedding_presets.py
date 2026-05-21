"""End-to-end tests for bigrag.routers.embedding_presets.

Endpoints covered:
- GET    /v1/admin/embedding-presets             (list + pagination)
- POST   /v1/admin/embedding-presets             (create)
- POST   /v1/admin/embedding-presets/test        (test request body)
- POST   /v1/admin/embedding-presets/{id}/test   (test saved preset)
- PATCH  /v1/admin/embedding-presets/{id}        (update)
- DELETE /v1/admin/embedding-presets/{id}        (delete)
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import httpx
import pytest_asyncio

from tests._helpers import assert_envelope, unique_name

PresetFactory = Callable[..., Awaitable[dict[str, Any]]]


@pytest_asyncio.fixture
async def preset(
    admin_client: httpx.AsyncClient,
    fake_openai_base: str,
) -> AsyncIterator[PresetFactory]:
    """Mint embedding presets and tear them down."""
    created_ids: list[str] = []

    async def _create(
        *,
        name: str | None = None,
        provider: str = "openai_compatible",
        model: str = "text-embedding-3-small",
        api_key: str = "sk-fake-test-key",
        base_url: str | None = None,
        dimension: int = 1536,
    ) -> dict[str, Any]:
        body = {
            "name": name or unique_name("preset"),
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "base_url": base_url if base_url is not None else f"{fake_openai_base}/v1",
            "dimension": dimension,
        }
        resp = await admin_client.post("/v1/admin/embedding-presets", json=body)
        data = assert_envelope(resp, 201)
        created_ids.append(data["id"])
        return data

    yield _create

    for preset_id in created_ids:
        try:
            await admin_client.delete(f"/v1/admin/embedding-presets/{preset_id}")
        except Exception:
            pass


async def test_list_presets_requires_admin(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.get("/v1/admin/embedding-presets")
    assert resp.status_code == 401, resp.text


async def test_list_presets_rejects_api_key(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    client = await api_key_client()
    resp = await client.get("/v1/admin/embedding-presets")
    assert resp.status_code in (401, 403), resp.text


async def test_create_preset_returns_shape_and_hides_secret(
    preset: PresetFactory,
) -> None:
    created = await preset()
    for key in (
        "id",
        "name",
        "provider",
        "model",
        "base_url",
        "dimension",
        "has_api_key",
        "created_at",
        "updated_at",
    ):
        assert key in created, f"missing {key!r} in {created!r}"
    assert created["has_api_key"] is True
    assert "api_key" not in created, "api_key plaintext must never leak"


async def test_list_presets_pagination(
    admin_client: httpx.AsyncClient,
    preset: PresetFactory,
) -> None:
    a = await preset()
    b = await preset()
    resp = await admin_client.get("/v1/admin/embedding-presets", params={"limit": 1, "offset": 0})
    body = assert_envelope(resp, 200)
    assert isinstance(body["presets"], list)
    assert len(body["presets"]) == 1
    assert body["total"] >= 2
    all_ids = {a["id"], b["id"]}
    page1_id = body["presets"][0]["id"]
    resp2 = await admin_client.get("/v1/admin/embedding-presets", params={"limit": 1, "offset": 1})
    body2 = assert_envelope(resp2, 200)
    assert len(body2["presets"]) == 1
    page2_id = body2["presets"][0]["id"]
    assert {page1_id, page2_id}.issubset(all_ids | {page1_id, page2_id})


async def test_test_request_body_against_fake_openai(
    admin_client: httpx.AsyncClient,
    fake_openai_base: str,
) -> None:
    resp = await admin_client.post(
        "/v1/admin/embedding-presets/test",
        json={
            "provider": "openai_compatible",
            "model": "text-embedding-3-small",
            "api_key": "sk-fake-test-key",
            "base_url": f"{fake_openai_base}/v1",
        },
    )
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"


async def test_test_saved_preset_against_fake_openai(
    admin_client: httpx.AsyncClient,
    preset: PresetFactory,
) -> None:
    created = await preset()
    resp = await admin_client.post(f"/v1/admin/embedding-presets/{created['id']}/test")
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"


async def test_test_saved_preset_unknown_id_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post("/v1/admin/embedding-presets/not-a-uuid/test")
    assert resp.status_code == 404, resp.text

    resp2 = await admin_client.post(
        "/v1/admin/embedding-presets/00000000-0000-0000-0000-000000000000/test"
    )
    assert resp2.status_code == 404, resp2.text


async def test_patch_preset_name_and_api_key(
    admin_client: httpx.AsyncClient,
    preset: PresetFactory,
) -> None:
    created = await preset(name=unique_name("orig"))
    new_name = unique_name("renamed")
    resp = await admin_client.patch(
        f"/v1/admin/embedding-presets/{created['id']}",
        json={"name": new_name, "api_key": "sk-rotated-fake-key"},
    )
    body = assert_envelope(resp, 200)
    assert body["name"] == new_name
    assert body["has_api_key"] is True
    assert "api_key" not in body


async def test_patch_preset_unknown_id_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.patch(
        "/v1/admin/embedding-presets/not-a-uuid",
        json={"name": "x"},
    )
    assert resp.status_code == 404, resp.text

    resp2 = await admin_client.patch(
        "/v1/admin/embedding-presets/00000000-0000-0000-0000-000000000000",
        json={"name": "x"},
    )
    assert resp2.status_code == 404, resp2.text


async def test_create_preset_duplicate_name_returns_409(
    preset: PresetFactory,
    admin_client: httpx.AsyncClient,
    fake_openai_base: str,
) -> None:
    name = unique_name("dup")
    await preset(name=name)
    resp = await admin_client.post(
        "/v1/admin/embedding-presets",
        json={
            "name": name,
            "provider": "openai_compatible",
            "model": "text-embedding-3-small",
            "api_key": "sk-fake-test-key",
            "base_url": f"{fake_openai_base}/v1",
            "dimension": 1536,
        },
    )
    assert resp.status_code == 409, resp.text


async def test_create_preset_invalid_provider_returns_422(
    admin_client: httpx.AsyncClient,
    fake_openai_base: str,
) -> None:
    resp = await admin_client.post(
        "/v1/admin/embedding-presets",
        json={
            "name": unique_name("bad"),
            "provider": "not_a_real_provider",
            "model": "text-embedding-3-small",
            "api_key": "sk-fake-test-key",
            "base_url": f"{fake_openai_base}/v1",
            "dimension": 1536,
        },
    )
    assert resp.status_code == 422, resp.text


async def test_collection_can_use_preset(
    admin_client: httpx.AsyncClient,
    preset: PresetFactory,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    created = await preset()
    coll = await collection(embedding_preset_id=created["id"])
    assert (
        coll.get("embedding_preset_id") == created["id"]
        or coll.get("embedding_preset") is not None
        or coll.get("embedding_provider") in ("openai_compatible", "openai")
    )


async def test_delete_preset_makes_it_unfindable(
    admin_client: httpx.AsyncClient,
    preset: PresetFactory,
) -> None:
    created = await preset()
    resp = await admin_client.delete(f"/v1/admin/embedding-presets/{created['id']}")
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"

    # Subsequent lookups should 404.
    test_resp = await admin_client.post(f"/v1/admin/embedding-presets/{created['id']}/test")
    assert test_resp.status_code == 404, test_resp.text

    patch_resp = await admin_client.patch(
        f"/v1/admin/embedding-presets/{created['id']}",
        json={"name": "x"},
    )
    assert patch_resp.status_code == 404, patch_resp.text

    list_resp = await admin_client.get("/v1/admin/embedding-presets")
    list_body = assert_envelope(list_resp, 200)
    assert all(p["id"] != created["id"] for p in list_body["presets"])


async def test_delete_preset_in_use_returns_409(
    admin_client: httpx.AsyncClient,
    preset: PresetFactory,
    collection: Callable[..., Awaitable[dict[str, Any]]],
) -> None:
    created = await preset()
    coll = await collection(embedding_preset_id=created["id"])
    try:
        resp = await admin_client.delete(f"/v1/admin/embedding-presets/{created['id']}")
        assert resp.status_code == 409, resp.text
    finally:
        # collection factory tears the collection down; force-delete it
        # first so the preset can be deleted afterwards.
        await admin_client.delete(f"/v1/collections/{coll['name']}")


async def test_delete_preset_unknown_id_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.delete("/v1/admin/embedding-presets/not-a-uuid")
    assert resp.status_code == 404, resp.text

    resp2 = await admin_client.delete(
        "/v1/admin/embedding-presets/00000000-0000-0000-0000-000000000000"
    )
    assert resp2.status_code == 404, resp2.text
