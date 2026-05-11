from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import httpx

from bigrag.db.models import (
    ConnectorAccount,
    ConnectorDocument,
    ConnectorProviderConfig,
    ConnectorSyncJob,
)
from bigrag.services.connector_core import (
    ConnectorSyncCounters,
    apply_counters,
    manifest_unchanged,
    oauth_redirect_url,
    sync_progress_details,
    sync_progress_percent,
)
from bigrag.services.connector_registry import connector_runtime
from bigrag.services.google_drive import (
    GOOGLE_DOC_MIME,
    GOOGLE_FOLDER_MIME,
    GOOGLE_PROVIDER,
    GoogleDriveClient,
    GoogleDriveConfigError,
    GoogleDriveNotFoundError,
    RemoteDriveFile,
    google_config_public,
    google_drive_file_public,
)


def run(coro):
    return asyncio.run(coro)


def test_google_connector_runtime_uses_shared_route_shape() -> None:
    runtime = connector_runtime("google")

    assert runtime is not None
    assert runtime.provider == GOOGLE_PROVIDER
    assert runtime.display_name == "Google Drive"
    assert connector_runtime("sharepoint") is None


def test_google_config_public_masks_secrets() -> None:
    config = ConnectorProviderConfig(
        provider=GOOGLE_PROVIDER,
        enabled=True,
        client_id="client-id.apps.googleusercontent.com",
        client_secret="secret",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    public = google_config_public(config, callback_url="http://localhost/callback")

    assert public["configured"] is True
    assert public["client_id"] == "client-id.apps.googleusercontent.com"
    assert public["has_client_secret"] is True
    assert "secret" not in public.values()


def test_oauth_redirect_url_uses_admin_origin() -> None:
    account = ConnectorAccount(
        provider=GOOGLE_PROVIDER,
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        meta={"redirect_origin": "https://admin.example.com"},
    )

    assert (
        oauth_redirect_url(account, "/collections/docs/connectors/google-drive")
        == "https://admin.example.com/collections/docs/connectors/google-drive"
    )


def test_google_drive_client_exports_workspace_document() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/drive/v3/files/doc-1/export"
        assert "mimeType=application%2Fvnd.openxmlformats-officedocument" in str(request.url)
        return httpx.Response(200, content=b"docx-bytes")

    client = GoogleDriveClient(transport=httpx.MockTransport(handler))
    remote = RemoteDriveFile(
        id="doc-1",
        name="Strategy",
        mime_type=GOOGLE_DOC_MIME,
        version="7",
    )

    downloaded = run(client.download("token", remote))

    assert len(requests) == 1
    assert downloaded.filename == "Strategy.docx"
    assert downloaded.file_ext == ".docx"
    assert downloaded.content == b"docx-bytes"


def test_google_drive_client_lists_folder_recursively() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        query = str(request.url.query)
        if path == "/drive/v3/files/root":
            return httpx.Response(
                200,
                json={"id": "root", "name": "Root", "mimeType": GOOGLE_FOLDER_MIME},
            )
        if path == "/drive/v3/files/folder-1":
            return httpx.Response(
                200,
                json={"id": "folder-1", "name": "Folder", "mimeType": GOOGLE_FOLDER_MIME},
            )
        if path == "/drive/v3/files" and b"%27root%27" in request.url.query:
            return httpx.Response(
                200,
                json={
                    "files": [
                        {"id": "file-1", "name": "A.pdf", "mimeType": "application/pdf"},
                        {
                            "id": "folder-1",
                            "name": "Folder",
                            "mimeType": GOOGLE_FOLDER_MIME,
                        },
                    ]
                },
            )
        if path == "/drive/v3/files" and b"%27folder-1%27" in request.url.query:
            return httpx.Response(
                200,
                json={"files": [{"id": "file-2", "name": "B.txt", "mimeType": "text/plain"}]},
            )
        raise AssertionError(f"Unexpected request: {path}?{query}")

    client = GoogleDriveClient(transport=httpx.MockTransport(handler))

    files = run(client.iter_files(access_token="token", root_id="root", source_type="folder"))

    assert [f.id for f in files] == ["file-1", "file-2"]


def test_google_drive_client_lists_browser_files() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/drive/v3/files"
        assert b"%27root%27+in+parents" in request.url.query
        assert b"pageToken" not in request.url.query
        return httpx.Response(
            200,
            json={
                "files": [
                    {"id": "folder-1", "name": "Folder", "mimeType": GOOGLE_FOLDER_MIME},
                    {"id": "file-1", "name": "A.pdf", "mimeType": "application/pdf"},
                ],
                "nextPageToken": "next",
            },
        )

    client = GoogleDriveClient(transport=httpx.MockTransport(handler))

    files, next_page_token = run(client.list_files(access_token="token", parent_id="root"))

    assert [f.id for f in files] == ["folder-1", "file-1"]
    assert next_page_token == "next"


def test_google_drive_client_maps_disabled_api_to_config_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "message": "Google Drive API has not been used in project 123 before",
                    "errors": [{"reason": "accessNotConfigured"}],
                    "details": [
                        {
                            "reason": "SERVICE_DISABLED",
                            "metadata": {"activationUrl": "https://console.example/enable"},
                        }
                    ],
                }
            },
        )

    client = GoogleDriveClient(transport=httpx.MockTransport(handler))

    try:
        run(client.list_files(access_token="token", parent_id="root"))
    except GoogleDriveConfigError as exc:
        assert "Google Drive API has not been used" in str(exc)
        assert "https://console.example/enable" in str(exc)
    else:
        raise AssertionError("Expected GoogleDriveConfigError")


def test_google_drive_file_public_marks_unsupported_files() -> None:
    remote = RemoteDriveFile(
        id="video-1",
        name="clip.mov",
        mime_type="video/quicktime",
    )

    public = google_drive_file_public(remote)

    assert public["source_type"] == "file"
    assert public["sync_supported"] is False
    assert public["unsupported_reason"] == "Unsupported file type .mov"


def test_google_drive_client_maps_404_to_not_found() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"message": "File not found"}})

    client = GoogleDriveClient(transport=httpx.MockTransport(handler))

    try:
        run(client.get_file("token", "missing"))
    except GoogleDriveNotFoundError:
        pass
    else:
        raise AssertionError("Expected GoogleDriveNotFoundError")


def test_manifest_unchanged_uses_remote_signature_before_hash() -> None:
    manifest = ConnectorDocument(
        source_id="00000000-0000-0000-0000-000000000001",
        document_id="00000000-0000-0000-0000-000000000002",
        remote_id="file-1",
        remote_name="A.pdf",
        remote_mime_type="application/pdf",
        remote_checksum="old-checksum",
        remote_version="v7",
        content_hash="old-content",
    )
    remote = RemoteDriveFile(
        id="file-1",
        name="A.pdf",
        mime_type="application/pdf",
        md5_checksum="old-checksum",
        version="v8",
    )

    assert manifest_unchanged(
        manifest,
        type(
            "Downloaded",
            (),
            {"remote": remote, "content_hash": "new-content"},
        )(),
    )


def test_sync_progress_percent_uses_phase_ranges() -> None:
    assert sync_progress_percent("queued") == 0
    assert sync_progress_percent("authenticating") == 5
    assert sync_progress_percent("scanning") == 12
    assert sync_progress_percent("syncing", processed_items=5, total_items=10) == 50
    assert sync_progress_percent("removing", processed_items=1, total_items=2) == 90
    assert sync_progress_percent("finalizing") == 98
    assert sync_progress_percent("complete") == 100
    assert sync_progress_percent("failed") == 100


def test_sync_progress_details_include_counts_and_current_item() -> None:
    counters = ConnectorSyncCounters(found=2, created=1, updated=1, skipped=2, deleted=3, failed=1)
    remote = RemoteDriveFile(
        id="file-1",
        name="Contract.pdf",
        mime_type="application/pdf",
    )

    progress = sync_progress_details(
        phase="syncing",
        message="Syncing Contract.pdf",
        counters=counters,
        current_item=remote,
        processed_items=1,
        total_items=2,
    )

    assert progress == {
        "phase": "syncing",
        "message": "Syncing Contract.pdf",
        "current_item_id": "file-1",
        "current_item_name": "Contract.pdf",
        "progress_percent": 50,
        "processed_items": 1,
        "total_items": 2,
        "counts": {
            "created": 1,
            "updated": 1,
            "skipped": 2,
            "deleted": 3,
            "failed": 1,
        },
    }


def test_apply_counters_preserves_existing_progress_details() -> None:
    job = ConnectorSyncJob(
        provider=GOOGLE_PROVIDER,
        source_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        trigger="manual",
        status="running",
        details={"progress": {"phase": "syncing"}, "other": True},
    )
    counters = ConnectorSyncCounters(found=4, created=1)
    counters.add_error("file-2", "Broken.pdf", "invalid content")

    apply_counters(job, counters)

    assert job.total_found == 4
    assert job.total_created == 1
    assert job.total_failed == 1
    assert job.details["progress"] == {"phase": "syncing"}
    assert job.details["errors"] == [
        {"remote_id": "file-2", "name": "Broken.pdf", "error": "invalid content"}
    ]
