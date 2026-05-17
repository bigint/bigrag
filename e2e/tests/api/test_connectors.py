"""End-to-end tests for bigrag.routers.connectors + bigrag.routers.admin_connectors.

Endpoints covered (admin_connectors):
- GET  /v1/admin/connectors/{provider_slug}
- PUT  /v1/admin/connectors/{provider_slug}

Endpoints covered (connectors):
- GET  /v1/connectors/{provider_slug}/account
- GET  /v1/connectors/{provider_slug}/oauth/start
- GET  /v1/connectors/{provider_slug}/oauth/start-url
- GET  /v1/connectors/{provider_slug}/oauth/callback
- GET  /v1/connectors/{provider_slug}/files
- GET  /v1/connectors/{provider_slug}/sources
- POST /v1/connectors/{provider_slug}/sources
- PATCH /v1/connectors/{provider_slug}/sources/{source_id}
- DELETE /v1/connectors/{provider_slug}/sources/{source_id}
- POST /v1/connectors/{provider_slug}/sources/{source_id}/sync
- GET  /v1/connectors/{provider_slug}/sync-jobs
- POST /v1/connectors/{provider_slug}/disconnect

Google OAuth URLs in ``bigrag.services.connectors.google_drive_*`` are
hardcoded to the real google.com / googleapis.com endpoints; full happy
path is not e2e-testable. The tests below cover everything reachable
without completing the OAuth exchange.
"""

from __future__ import annotations

import httpx

from tests._helpers import assert_envelope

PROVIDER = "google"
PROVIDER_CANONICAL = "google_drive"


async def _reset_provider_config(admin_client: httpx.AsyncClient) -> None:
    await admin_client.put(
        f"/v1/admin/connectors/{PROVIDER}",
        json={"enabled": False, "client_id": "", "client_secret": ""},
    )


# ---------------------------------------------------------------------------
# Admin: connector config CRUD
# ---------------------------------------------------------------------------


async def test_admin_get_connector_config_returns_shape(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get(f"/v1/admin/connectors/{PROVIDER}")
    body = assert_envelope(resp, 200)
    for key in (
        "provider",
        "configured",
        "enabled",
        "client_id",
        "has_client_secret",
        "callback_url",
    ):
        assert key in body, f"missing {key!r} in {body!r}"
    assert body["provider"] in (PROVIDER, PROVIDER_CANONICAL)
    assert "oauth/callback" in body["callback_url"]


async def test_admin_get_connector_config_unknown_provider_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/admin/connectors/notreal")
    assert resp.status_code == 404


async def test_admin_update_connector_config_round_trips(
    admin_client: httpx.AsyncClient,
) -> None:
    try:
        resp = await admin_client.put(
            f"/v1/admin/connectors/{PROVIDER}",
            json={
                "enabled": True,
                "client_id": "fake-client-id.apps.googleusercontent.com",
                "client_secret": "fake-secret-value",
            },
        )
        body = assert_envelope(resp, 200)
        assert body["enabled"] is True
        assert body["client_id"] == "fake-client-id.apps.googleusercontent.com"
        assert body["has_client_secret"] is True
        assert body["configured"] is True

        resp = await admin_client.get(f"/v1/admin/connectors/{PROVIDER}")
        again = assert_envelope(resp, 200)
        assert again["enabled"] is True
        assert again["client_id"] == "fake-client-id.apps.googleusercontent.com"
    finally:
        await _reset_provider_config(admin_client)


async def test_admin_update_connector_unknown_provider_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.put(
        "/v1/admin/connectors/notreal",
        json={"enabled": True, "client_id": "x", "client_secret": "y"},
    )
    assert resp.status_code == 404


async def test_admin_connector_endpoints_require_admin(
    unauth_client: httpx.AsyncClient,
) -> None:
    resp = await unauth_client.get(f"/v1/admin/connectors/{PROVIDER}")
    assert resp.status_code == 401

    resp = await unauth_client.put(
        f"/v1/admin/connectors/{PROVIDER}",
        json={"enabled": True, "client_id": "x"},
    )
    assert resp.status_code == 401


async def test_admin_connector_endpoints_reject_api_key(
    api_key_client,
) -> None:
    client = await api_key_client()
    resp = await client.get(f"/v1/admin/connectors/{PROVIDER}")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# User: account / oauth / disconnect (no connected account required)
# ---------------------------------------------------------------------------


async def test_get_account_unconfigured(
    admin_client: httpx.AsyncClient,
) -> None:
    await _reset_provider_config(admin_client)
    resp = await admin_client.get(f"/v1/connectors/{PROVIDER}/account")
    body = assert_envelope(resp, 200)
    assert body["provider"] in (PROVIDER, PROVIDER_CANONICAL)
    assert body["configured"] is False
    assert body["connected"] is False


async def test_oauth_start_url_requires_config(
    admin_client: httpx.AsyncClient,
) -> None:
    await _reset_provider_config(admin_client)
    resp = await admin_client.get(f"/v1/connectors/{PROVIDER}/oauth/start-url")
    assert resp.status_code == 400


async def test_oauth_start_url_returns_consent_url(
    admin_client: httpx.AsyncClient,
) -> None:
    try:
        await admin_client.put(
            f"/v1/admin/connectors/{PROVIDER}",
            json={
                "enabled": True,
                "client_id": "fake-client-id.apps.googleusercontent.com",
                "client_secret": "fake-secret-value",
            },
        )
        resp = await admin_client.get(f"/v1/connectors/{PROVIDER}/oauth/start-url")
        body = assert_envelope(resp, 200)
        assert "auth_url" in body
        auth_url = body["auth_url"]
        assert "client_id=fake-client-id" in auth_url
        assert "response_type=code" in auth_url
        assert "state=" in auth_url
        assert "scope=" in auth_url
        # callback URL is URL-encoded in the redirect_uri query param
        assert "oauth%2Fcallback" in auth_url or "oauth/callback" in auth_url
    finally:
        await _reset_provider_config(admin_client)


async def test_oauth_start_redirects(
    admin_client: httpx.AsyncClient,
) -> None:
    try:
        await admin_client.put(
            f"/v1/admin/connectors/{PROVIDER}",
            json={
                "enabled": True,
                "client_id": "fake-client-id.apps.googleusercontent.com",
                "client_secret": "fake-secret-value",
            },
        )
        async with httpx.AsyncClient(
            base_url=str(admin_client.base_url),
            cookies=admin_client.cookies,
            follow_redirects=False,
            timeout=10.0,
        ) as no_follow:
            resp = await no_follow.get(f"/v1/connectors/{PROVIDER}/oauth/start")
        assert resp.status_code in (302, 303, 307)
        assert "accounts.google.com" in resp.headers.get("location", "")
    finally:
        await _reset_provider_config(admin_client)


async def test_oauth_callback_missing_code_returns_400(
    admin_client: httpx.AsyncClient,
) -> None:
    try:
        await admin_client.put(
            f"/v1/admin/connectors/{PROVIDER}",
            json={
                "enabled": True,
                "client_id": "fake-client-id.apps.googleusercontent.com",
                "client_secret": "fake-secret-value",
            },
        )
        async with httpx.AsyncClient(
            base_url=str(admin_client.base_url),
            cookies=admin_client.cookies,
            follow_redirects=False,
            timeout=10.0,
        ) as no_follow:
            resp = await no_follow.get(f"/v1/connectors/{PROVIDER}/oauth/callback")
        assert resp.status_code == 400
    finally:
        await _reset_provider_config(admin_client)


async def test_oauth_callback_with_error_redirects(
    admin_client: httpx.AsyncClient,
) -> None:
    try:
        await admin_client.put(
            f"/v1/admin/connectors/{PROVIDER}",
            json={
                "enabled": True,
                "client_id": "fake-client-id.apps.googleusercontent.com",
                "client_secret": "fake-secret-value",
            },
        )
        async with httpx.AsyncClient(
            base_url=str(admin_client.base_url),
            cookies=admin_client.cookies,
            follow_redirects=False,
            timeout=10.0,
        ) as no_follow:
            resp = await no_follow.get(
                f"/v1/connectors/{PROVIDER}/oauth/callback",
                params={"error": "access_denied", "state": "some-state"},
            )
        assert resp.status_code in (302, 303, 307)
        assert "google_error=access_denied" in resp.headers.get("location", "")
    finally:
        await _reset_provider_config(admin_client)


# ---------------------------------------------------------------------------
# Files / sources / sync-jobs without a connected account
# ---------------------------------------------------------------------------


async def test_files_requires_connected_account(
    admin_client: httpx.AsyncClient,
) -> None:
    try:
        await admin_client.put(
            f"/v1/admin/connectors/{PROVIDER}",
            json={
                "enabled": True,
                "client_id": "fake-client-id.apps.googleusercontent.com",
                "client_secret": "fake-secret-value",
            },
        )
        resp = await admin_client.get(f"/v1/connectors/{PROVIDER}/files")
        assert resp.status_code in (400, 401, 404, 502)
    finally:
        await _reset_provider_config(admin_client)


async def test_list_sources_empty(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get(f"/v1/connectors/{PROVIDER}/sources")
    body = assert_envelope(resp, 200)
    assert "sources" in body
    assert "total" in body
    assert isinstance(body["sources"], list)


async def test_list_sources_filter_by_collection(
    admin_client: httpx.AsyncClient,
    collection,
) -> None:
    coll = await collection()
    resp = await admin_client.get(
        f"/v1/connectors/{PROVIDER}/sources",
        params={"collection": coll["name"]},
    )
    body = assert_envelope(resp, 200)
    assert isinstance(body["sources"], list)
    assert body["total"] == 0


async def test_sync_jobs_empty(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get(f"/v1/connectors/{PROVIDER}/sync-jobs")
    body = assert_envelope(resp, 200)
    assert "jobs" in body
    assert "total" in body


async def test_sync_jobs_filter_by_source(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get(
        f"/v1/connectors/{PROVIDER}/sync-jobs",
        params={"source_id": "00000000-0000-0000-0000-000000000000"},
    )
    body = assert_envelope(resp, 200)
    assert body["total"] == 0


async def test_sync_jobs_invalid_source_id_400(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get(
        f"/v1/connectors/{PROVIDER}/sync-jobs",
        params={"source_id": "not-a-uuid"},
    )
    assert resp.status_code == 400


async def test_create_source_without_account_fails(
    admin_client: httpx.AsyncClient,
    collection,
) -> None:
    try:
        await admin_client.put(
            f"/v1/admin/connectors/{PROVIDER}",
            json={
                "enabled": True,
                "client_id": "fake-client-id.apps.googleusercontent.com",
                "client_secret": "fake-secret-value",
            },
        )
        coll = await collection()
        resp = await admin_client.post(
            f"/v1/connectors/{PROVIDER}/sources",
            json={
                "collection_name": coll["name"],
                "root_id": "doc-1",
                "root_name": "Acme Onboarding.gdoc",
                "root_mime_type": "application/vnd.google-apps.document",
                "source_type": "file",
            },
        )
        assert resp.status_code in (400, 401, 404), resp.text
    finally:
        await _reset_provider_config(admin_client)


async def test_update_source_404_for_unknown(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.patch(
        f"/v1/connectors/{PROVIDER}/sources/00000000-0000-0000-0000-000000000000",
        json={"schedule_enabled": True, "sync_interval_hours": 6},
    )
    assert resp.status_code == 404


async def test_delete_source_404_for_unknown(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.delete(
        f"/v1/connectors/{PROVIDER}/sources/00000000-0000-0000-0000-000000000000"
    )
    assert resp.status_code == 404


async def test_sync_source_404_for_unknown(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(
        f"/v1/connectors/{PROVIDER}/sources/00000000-0000-0000-0000-000000000000/sync"
    )
    assert resp.status_code == 404


async def test_disconnect_is_idempotent(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.post(f"/v1/connectors/{PROVIDER}/disconnect")
    body = assert_envelope(resp, 200)
    assert body["status"] == "ok"


# ---------------------------------------------------------------------------
# Authn
# ---------------------------------------------------------------------------


async def test_connector_endpoints_require_session(
    unauth_client: httpx.AsyncClient,
) -> None:
    for path in (
        f"/v1/connectors/{PROVIDER}/account",
        f"/v1/connectors/{PROVIDER}/files",
        f"/v1/connectors/{PROVIDER}/sources",
        f"/v1/connectors/{PROVIDER}/sync-jobs",
        f"/v1/connectors/{PROVIDER}/oauth/start-url",
    ):
        resp = await unauth_client.get(path)
        assert resp.status_code == 401, (path, resp.status_code)


async def test_unknown_provider_404_on_user_routes(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/connectors/notreal/account")
    assert resp.status_code == 404
    resp = await admin_client.get("/v1/connectors/notreal/sources")
    assert resp.status_code == 404
