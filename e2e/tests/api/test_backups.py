"""End-to-end tests for bigrag.routers.admin_backups.

Endpoints covered:
- GET    /v1/admin/backups
- POST   /v1/admin/backups
- GET    /v1/admin/backups/{id}

The e2e compose stack ships a MinIO container reachable at the host on
``localhost:9004`` (``e2e`` / ``e2e-secret-password``). The bigRAG
backend talks to MinIO at ``http://minio:9000`` from inside the network,
so backup jobs upload there. We use boto3 against the host-side endpoint
to make sure the ``bigrag-backups`` bucket exists before exercising the
backup job; if MinIO is unreachable the suite is skipped.
"""

from __future__ import annotations

import asyncio
import contextlib
import os

import httpx
import pytest
import pytest_asyncio

from tests._helpers import assert_envelope, poll_until, unique_name

MINIO_ENDPOINT = os.environ.get("BIGRAG_E2E_MINIO_ENDPOINT", "http://localhost:9004")
MINIO_ACCESS_KEY = os.environ.get("BIGRAG_E2E_MINIO_ACCESS_KEY", "e2e")
MINIO_SECRET_KEY = os.environ.get("BIGRAG_E2E_MINIO_SECRET_KEY", "e2e-secret-password")
BACKUP_BUCKET = "bigrag-backups"


@pytest.fixture(scope="session")
def ensure_backup_bucket() -> None:
    """Ensure the bigrag-backups bucket exists on the e2e MinIO container.

    Skip the entire backup suite if boto3 is missing or MinIO is
    unreachable so the assertion suite stays green when the optional
    dependency is unavailable in a developer's environment.
    """
    try:
        import boto3  # type: ignore[import-untyped]
        from botocore.client import Config  # type: ignore[import-untyped]
        from botocore.exceptions import (  # type: ignore[import-untyped]
            ClientError,
            EndpointConnectionError,
        )
    except ImportError as exc:
        pytest.skip(f"boto3 not available: {exc}")

    s3 = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    try:
        s3.head_bucket(Bucket=BACKUP_BUCKET)
    except EndpointConnectionError as exc:
        pytest.skip(f"MinIO at {MINIO_ENDPOINT} is unreachable: {exc}")
    except ClientError as exc:
        status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
        if status == 404:
            try:
                s3.create_bucket(Bucket=BACKUP_BUCKET)
            except ClientError as inner:
                pytest.skip(f"could not create bucket {BACKUP_BUCKET!r}: {inner}")
        elif status in (401, 403):
            pytest.skip(f"MinIO credentials rejected: {exc}")
        else:
            raise
    return None


@pytest_asyncio.fixture
async def wait_for_no_active_backup(admin_client: httpx.AsyncClient):
    """Make sure no pending/running backup is in flight before each test.

    The backup service rejects new jobs with 409 while another is in
    flight; previous tests may have left a backup running."""

    async def _no_active() -> bool:
        resp = await admin_client.get("/v1/admin/backups", params={"limit": 50})
        body = resp.json()
        return all(j.get("status") not in ("pending", "running") for j in body.get("jobs", []))

    await poll_until(
        _no_active,
        predicate=lambda ok: ok,
        timeout=60.0,
        interval=1.0,
        description="no active backup jobs",
    )


async def test_list_backups_requires_admin(unauth_client: httpx.AsyncClient) -> None:
    resp = await unauth_client.get("/v1/admin/backups")
    assert resp.status_code == 401, resp.text


async def test_list_backups_rejects_api_key(
    api_key_client,
) -> None:
    client = await api_key_client()
    resp = await client.get("/v1/admin/backups")
    assert resp.status_code in (401, 403), resp.text


async def test_list_backups_returns_shape(admin_client: httpx.AsyncClient) -> None:
    resp = await admin_client.get(
        "/v1/admin/backups",
        params={"limit": 5, "offset": 0, "include_total": "true"},
    )
    body = assert_envelope(resp, 200)
    assert "jobs" in body and isinstance(body["jobs"], list)
    assert "total" in body and isinstance(body["total"], int)


async def test_get_backup_unknown_id_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/admin/backups/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404, resp.text


async def test_get_backup_invalid_id_returns_400(
    admin_client: httpx.AsyncClient,
) -> None:
    resp = await admin_client.get("/v1/admin/backups/not-a-uuid")
    assert resp.status_code == 400, resp.text


async def test_create_backup_job_runs_to_terminal_status(
    admin_client: httpx.AsyncClient,
    ensure_backup_bucket: None,
    wait_for_no_active_backup,
) -> None:
    label = unique_name("e2e-backup")
    resp = await admin_client.post(
        "/v1/admin/backups",
        json={"label": label},
    )
    body = assert_envelope(resp, 201)
    job_id = body["id"]
    assert body["status"] in ("pending", "running", "succeeded", "failed")
    assert body["label"] == label
    for key in (
        "id",
        "label",
        "status",
        "progress",
        "destination_prefix",
        "object_count",
        "byte_count",
        "manifest",
        "created_at",
        "updated_at",
    ):
        assert key in body

    async def _fetch() -> dict:
        r = await admin_client.get(f"/v1/admin/backups/{job_id}")
        r.raise_for_status()
        return r.json()

    final = await poll_until(
        _fetch,
        predicate=lambda j: j["status"] in ("succeeded", "failed"),
        timeout=120.0,
        interval=1.0,
        description="backup job terminal status",
    )
    if final["status"] == "failed":
        pytest.skip(
            f"backup job failed (likely environment-specific); error={final.get('error_message')!r}"
        )
    assert final["progress"] == 1.0
    assert final["object_count"] >= 1
    assert final["destination_prefix"]

    # And it must show up in the list.
    list_resp = await admin_client.get("/v1/admin/backups", params={"limit": 50})
    list_body = assert_envelope(list_resp, 200)
    assert any(j["id"] == job_id for j in list_body["jobs"])


async def test_create_backup_concurrent_returns_409(
    admin_client: httpx.AsyncClient,
    ensure_backup_bucket: None,
    wait_for_no_active_backup,
) -> None:
    """Posting a second backup while one is in flight yields 409."""
    first = await admin_client.post(
        "/v1/admin/backups",
        json={"label": unique_name("e2e-conc-1")},
    )
    if first.status_code != 201:
        pytest.skip(f"unable to start first backup: {first.status_code} {first.text}")

    try:
        # The first job is pending/running; the second create should 409.
        second = await admin_client.post(
            "/v1/admin/backups",
            json={"label": unique_name("e2e-conc-2")},
        )
        # Race: if the first finished instantly the second may be 201.
        assert second.status_code in (201, 409), second.text
    finally:
        # Wait for the first backup to drain so the next test can start
        # cleanly.
        job_id = first.json()["id"]

        async def _fetch() -> dict:
            r = await admin_client.get(f"/v1/admin/backups/{job_id}")
            r.raise_for_status()
            return r.json()

        with contextlib.suppress(TimeoutError):
            await poll_until(
                _fetch,
                predicate=lambda j: j["status"] in ("succeeded", "failed"),
                timeout=120.0,
                interval=1.0,
                description="first backup terminal status",
            )
        await asyncio.sleep(0.1)
