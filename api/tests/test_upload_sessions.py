from __future__ import annotations

import uuid
from datetime import UTC, datetime

from bigrag.db.models import UploadSession, UploadSessionItem
from bigrag.routers.upload_sessions import _counts, _effective_item_status, _session_status


def _item(status: str = "queued") -> UploadSessionItem:
    now = datetime.now(UTC)
    return UploadSessionItem(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        client_item_id=str(uuid.uuid4()),
        filename="file.txt",
        file_type="txt",
        file_size=5,
        status=status,
        created_at=now,
        updated_at=now,
    )


def _session(total_files: int = 3, status: str = "preparing") -> UploadSession:
    now = datetime.now(UTC)
    return UploadSession(
        id=uuid.uuid4(),
        collection_id=uuid.uuid4(),
        collection_name="docs",
        status=status,
        total_files=total_files,
        total_bytes=15,
        created_at=now,
        updated_at=now,
        meta={},
    )


def test_effective_item_status_follows_document_state() -> None:
    item = _item()

    assert _effective_item_status(item, "processing") == "ingesting"
    assert _effective_item_status(item, "ready") == "complete"
    assert _effective_item_status(item, "failed") == "failed"


def test_counts_project_document_statuses() -> None:
    rows = [
        (_item(), "pending", None),
        (_item(), "processing", None),
        (_item(), "ready", None),
        (_item("failed"), None, "bad file"),
    ]

    counts = _counts(rows)

    assert counts["uploaded_files"] == 4
    assert counts["queued_files"] == 1
    assert counts["processing_files"] == 1
    assert counts["completed_files"] == 1
    assert counts["failed_files"] == 1


def test_session_status_tracks_upload_and_ingestion_phases() -> None:
    upload_session = _session(total_files=2)

    assert _session_status(upload_session, _counts([])) == "preparing"
    assert _session_status(upload_session, _counts([(_item(), "pending", None)])) == "uploading"
    assert (
        _session_status(
            upload_session,
            _counts([(_item(), "pending", None), (_item(), "processing", None)]),
        )
        == "ingesting"
    )
    assert (
        _session_status(
            upload_session,
            _counts([(_item(), "ready", None), (_item(), "ready", None)]),
        )
        == "complete"
    )


def test_session_status_preserves_canceled() -> None:
    upload_session = _session(total_files=1, status="canceled")

    assert _session_status(upload_session, _counts([(_item(), "ready", None)])) == "canceled"
