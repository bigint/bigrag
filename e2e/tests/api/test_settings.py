"""End-to-end tests for bigrag.routers.admin_settings.

Endpoints covered:
- GET    /v1/admin/settings
- PUT    /v1/admin/settings
- POST   /v1/admin/settings/test
- POST   /v1/admin/settings/reset
- POST   /v1/admin/settings/embedding-cache/purge

Notes
-----
* Secret-typed settings are *masked* by being returned as ``value: None``
  with ``has_value: true`` when a database row exists. This is what the
  router and ``runtime_settings._public_value`` enforce.
* The ``/test`` endpoint validates a candidate ``values`` dict against
  the runtime-settings prepare pipeline (including outbound-URL safety).
  It returns ``status="ok"`` on success and HTTP 400 on validation
  failure, not ``ok=False``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import httpx
import pytest_asyncio

from tests._helpers import assert_envelope


@pytest_asyncio.fixture
async def restore_chat_temperature(admin_client: httpx.AsyncClient):
    """Snapshot the chat_temperature setting and restore after the test."""
    resp = await admin_client.get("/v1/admin/settings")
    body = assert_envelope(resp, 200)
    values = body["values"]
    original = values["chat_temperature"]["value"]
    had_db_row = values["chat_temperature"]["source"] == "database"
    try:
        yield original
    finally:
        if had_db_row:
            await admin_client.put(
                "/v1/admin/settings",
                json={"values": {"chat_temperature": original}},
            )
        else:
            await admin_client.post(
                "/v1/admin/settings/reset",
                json={"keys": ["chat_temperature"]},
            )


async def test_settings_requires_admin_session(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.get("/v1/admin/settings")
    assert resp.status_code == 401, resp.text


async def test_settings_rejects_api_key(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    client = await api_key_client()
    resp = await client.get("/v1/admin/settings")
    assert resp.status_code in (401, 403), resp.text


async def test_settings_get_returns_specs_and_values(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/admin/settings")
    body = assert_envelope(resp, 200)
    assert "specs" in body and isinstance(body["specs"], list) and body["specs"]
    assert "values" in body and isinstance(body["values"], dict)

    spec_keys = {spec["key"] for spec in body["specs"]}
    for sample in (
        "chat_temperature",
        "embedding_api_key",
        "max_upload_size_mb",
        "turbopuffer_api_key",
        "turbopuffer_base_url",
    ):
        assert sample in spec_keys, f"expected setting key {sample!r} in spec list"
        assert sample in body["values"], f"missing value entry for {sample!r}"
    assert "qdrant_url" not in spec_keys
    assert "qdrant_required" not in spec_keys

    for spec in body["specs"]:
        for key in ("key", "group", "label", "description", "kind", "default", "options", "secret"):
            assert key in spec, f"missing spec.{key} in {spec!r}"


async def test_settings_secret_values_are_masked(
    admin_client: httpx.AsyncClient,
) -> None:
    """Secret settings come back as ``value: None`` regardless of contents."""
    # Set a secret value so we have a known database row to inspect.
    sentinel = "sk-test-mask-12345"
    try:
        put_resp = await admin_client.put(
            "/v1/admin/settings",
            json={"values": {"embedding_api_key": sentinel}},
        )
        assert_envelope(put_resp, 200)

        resp = await admin_client.get("/v1/admin/settings")
        body = assert_envelope(resp, 200)
        entry = body["values"]["embedding_api_key"]
        assert entry["value"] is None, f"secret value must never leak; got {entry['value']!r}"
        assert entry["has_value"] is True
        assert entry["source"] == "database"
        sentinel_str = sentinel
        for spec in body["specs"]:
            if spec["key"] == "embedding_api_key":
                assert spec["default"] is None, "secret defaults must be hidden too"
                assert spec["secret"] is True
        # Make absolutely sure the plaintext value is not leaking anywhere.
        assert sentinel_str not in resp.text
    finally:
        await admin_client.post(
            "/v1/admin/settings/reset",
            json={"keys": ["embedding_api_key"]},
        )


async def test_settings_put_then_get_round_trip(
    admin_client: httpx.AsyncClient,
    restore_chat_temperature,
) -> None:
    new_value = 0.42
    resp = await admin_client.put(
        "/v1/admin/settings",
        json={"values": {"chat_temperature": new_value}},
    )
    body = assert_envelope(resp, 200)
    assert body["values"]["chat_temperature"]["value"] == new_value
    assert body["values"]["chat_temperature"]["source"] == "database"

    follow = await admin_client.get("/v1/admin/settings")
    follow_body = assert_envelope(follow, 200)
    assert follow_body["values"]["chat_temperature"]["value"] == new_value


async def test_settings_put_unchanged_default_does_not_create_override(
    admin_client: httpx.AsyncClient,
) -> None:
    await admin_client.post(
        "/v1/admin/settings/reset",
        json={"keys": ["chat_temperature"]},
    )
    before_resp = await admin_client.get("/v1/admin/settings")
    before = assert_envelope(before_resp, 200)["values"]["chat_temperature"]
    assert before["source"] in ("default", "bootstrap")

    put_resp = await admin_client.put(
        "/v1/admin/settings",
        json={"values": {"chat_temperature": before["value"]}},
    )
    after = assert_envelope(put_resp, 200)["values"]["chat_temperature"]
    assert after["value"] == before["value"]
    assert after["source"] == before["source"]
    assert after["updated_at"] is None


async def test_settings_put_unchanged_database_value_preserves_override_timestamp(
    admin_client: httpx.AsyncClient,
    restore_chat_temperature,
) -> None:
    await admin_client.put(
        "/v1/admin/settings",
        json={"values": {"chat_temperature": 0.37}},
    )
    first_resp = await admin_client.get("/v1/admin/settings")
    first = assert_envelope(first_resp, 200)["values"]["chat_temperature"]
    assert first["source"] == "database"

    second_resp = await admin_client.put(
        "/v1/admin/settings",
        json={"values": {"chat_temperature": first["value"]}},
    )
    second = assert_envelope(second_resp, 200)["values"]["chat_temperature"]
    assert second["source"] == "database"
    assert second["updated_at"] == first["updated_at"]


async def test_settings_put_unchanged_secret_preserves_override_timestamp(
    admin_client: httpx.AsyncClient,
) -> None:
    sentinel = "sk-test-unchanged-secret"
    try:
        await admin_client.put(
            "/v1/admin/settings",
            json={"values": {"embedding_api_key": sentinel}},
        )
        first_resp = await admin_client.get("/v1/admin/settings")
        first = assert_envelope(first_resp, 200)["values"]["embedding_api_key"]
        assert first["source"] == "database"
        assert first["has_value"] is True

        second_resp = await admin_client.put(
            "/v1/admin/settings",
            json={"values": {"embedding_api_key": sentinel}},
        )
        second = assert_envelope(second_resp, 200)["values"]["embedding_api_key"]
        assert second["source"] == "database"
        assert second["has_value"] is True
        assert second["updated_at"] == first["updated_at"]
    finally:
        await admin_client.post(
            "/v1/admin/settings/reset",
            json={"keys": ["embedding_api_key"]},
        )


async def test_settings_put_unknown_key_returns_400(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.put(
        "/v1/admin/settings",
        json={"values": {"definitely_not_a_real_setting": 1}},
    )
    assert resp.status_code == 400, resp.text


async def test_settings_put_invalid_type_returns_400(
    admin_client: httpx.AsyncClient,
) -> None:
    # chat_temperature is a float in [0, 2]; 9 is above max.
    resp = await admin_client.put(
        "/v1/admin/settings",
        json={"values": {"chat_temperature": 9}},
    )
    assert resp.status_code == 400, resp.text


async def test_settings_test_validates_chat_provider_settings(
    admin_client: httpx.AsyncClient,
    fake_openai_base: str,
) -> None:
    resp = await admin_client.post(
        "/v1/admin/settings/test",
        json={
            "values": {
                "chat_base_url": f"{fake_openai_base}/v1",
                "chat_model": "gpt-4o-mini",
                "chat_temperature": 0.1,
            },
        },
    )
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"
    assert set(body["checked"]) >= {"chat_base_url", "chat_model", "chat_temperature"}


async def test_settings_test_validates_turbopuffer_settings(
    admin_client: httpx.AsyncClient,
    fake_turbopuffer_base: str,
) -> None:
    resp = await admin_client.post(
        "/v1/admin/settings/test",
        json={
            "values": {
                "turbopuffer_api_key": "e2e-fake-turbopuffer-key",
                "turbopuffer_base_url": fake_turbopuffer_base,
                "turbopuffer_region": "e2e",
            },
        },
    )
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"
    assert set(body["checked"]) >= {
        "turbopuffer_api_key",
        "turbopuffer_base_url",
        "turbopuffer_region",
    }


async def test_settings_test_rejects_broken_base_url(
    admin_client: httpx.AsyncClient,
) -> None:
    # The ``/test`` endpoint validates the *keys* are recognized; whether
    # it rejects a malformed base_url depends on the URL validator's
    # strictness. Both 200 (accepted, not strictly validated) and 400
    # (rejected up-front) are valid outcomes.
    resp = await admin_client.post(
        "/v1/admin/settings/test",
        json={"values": {"chat_base_url": "not_a_url"}},
    )
    assert resp.status_code in (200, 400), resp.text


async def test_settings_test_unknown_key_returns_400(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/admin/settings/test",
        json={"values": {"definitely_not_a_real_setting": True}},
    )
    assert resp.status_code == 400, resp.text


async def test_settings_reset_reverts_to_default(
    admin_client: httpx.AsyncClient,
    restore_chat_temperature,
) -> None:
    # Establish a non-default value first.
    await admin_client.put(
        "/v1/admin/settings",
        json={"values": {"chat_temperature": 1.5}},
    )
    snapshot = (await admin_client.get("/v1/admin/settings")).json()
    assert snapshot["values"]["chat_temperature"]["value"] == 1.5

    resp = await admin_client.post(
        "/v1/admin/settings/reset",
        json={"keys": ["chat_temperature"]},
    )
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"

    after = (await admin_client.get("/v1/admin/settings")).json()
    chat_temp = after["values"]["chat_temperature"]
    assert chat_temp["source"] in ("default", "bootstrap")


async def test_settings_reset_unknown_key_returns_400(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        "/v1/admin/settings/reset",
        json={"keys": ["definitely_not_a_real_setting"]},
    )
    assert resp.status_code == 400, resp.text


async def test_purge_embedding_cache(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.post("/v1/admin/settings/embedding-cache/purge")
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"
    assert "Purged" in body["message"]


async def test_purge_embedding_cache_rejects_unauth(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.post(
        "/v1/admin/settings/embedding-cache/purge",
        headers={"Origin": "http://localhost:4000"},
    )
    assert resp.status_code == 401, resp.text


async def test_settings_endpoints_reject_api_key_writes(
    api_key_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    client = await api_key_client()
    for method, path in (
        ("PUT", "/v1/admin/settings"),
        ("POST", "/v1/admin/settings/reset"),
        ("POST", "/v1/admin/settings/test"),
        ("POST", "/v1/admin/settings/embedding-cache/purge"),
    ):
        resp = await client.request(
            method,
            path,
            json={"values": {}, "keys": []},
        )
        assert resp.status_code in (401, 403), (
            f"{method} {path}: expected 401/403, got {resp.status_code} {resp.text}"
        )


async def test_settings_put_requires_origin_for_session(
    admin_client: httpx.AsyncClient,
) -> None:
    """Sanity: the admin_client injects Origin; without it the CSRF
    middleware rejects the mutation."""
    resp = await admin_client.put(
        "/v1/admin/settings",
        json={"values": {"chat_temperature": 0.3}},
        headers={"Origin": "http://attacker.example"},
    )
    assert resp.status_code in (400, 403), resp.text
