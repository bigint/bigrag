from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bigrag.db.models import EmbeddingCache
from bigrag.middleware.maintenance import MaintenanceWriteLockMiddleware
from bigrag.services import crypto, embedding_cache
from bigrag.services.backup import (
    BACKUP_FORMAT_VERSION,
    BackupUploadStats,
    _manifest,
    _point_payload,
    _row_payload,
)
from bigrag.services.storage import LocalStorage


@pytest.fixture(autouse=True)
def reset_crypto() -> None:
    crypto.configure(None)
    yield
    crypto.configure(None)


def test_manifest_records_readable_redacted_backup() -> None:
    stats = BackupUploadStats()
    target = SimpleNamespace(
        bucket="bigrag-backups",
        endpoint_url="https://example.r2.cloudflarestorage.com",
        region="auto",
    )

    manifest = _manifest(
        job_id=uuid.uuid4(),
        target=target,
        backup_prefix="prod/backups/backup-id",
        table_counts={"collections": 1},
        vector_counts={"docs": 2},
        upload_count=3,
        stats=stats,
    )

    assert manifest["format_version"] == BACKUP_FORMAT_VERSION
    assert manifest["encryption"] == "redacted"
    assert manifest["redaction"] == {
        "secret_columns": True,
        "embedding_cache_vectors": True,
        "raw_uploads": False,
    }
    assert manifest["destination"]["bucket"] == "bigrag-backups"
    assert manifest["tables"] == {"collections": 1}
    assert manifest["vectors"] == {"docs": 2}
    assert manifest["uploads"] == {"files": 3}


def test_embedding_cache_row_redacts_vector() -> None:
    crypto.configure(Fernet.generate_key().decode())
    row = EmbeddingCache(
        content_hash="hash",
        model_key="openai:text-embedding-3-small:3",
        vector=embedding_cache._encode_vector([0.1, -0.2, 3.5]),
        dimension=3,
        created_at=datetime.now(UTC),
        last_hit_at=datetime.now(UTC),
    )

    payload = _row_payload(row, sa.inspect(EmbeddingCache))

    assert payload["vector"] == "[REDACTED]"
    assert payload["content_hash"] == "hash"


def test_qdrant_point_payload_is_json_readable() -> None:
    point = SimpleNamespace(
        id=uuid.uuid4(),
        payload={"document_id": "doc", "page_no": 3},
        vector=[0.1, 0.2],
    )

    payload = _point_payload(point)

    assert payload["payload"] == {"document_id": "doc", "page_no": 3}
    assert payload["vector"] == [0.1, 0.2]


def test_local_storage_missing_upload_fails(tmp_path) -> None:
    storage = LocalStorage(str(tmp_path / "uploads"))

    with pytest.raises(FileNotFoundError):
        asyncio.run(storage.write_to_path("missing.pdf", tmp_path / "out" / "missing.pdf"))


def test_maintenance_lock_blocks_mutating_routes(monkeypatch) -> None:
    app = FastAPI()
    app.add_middleware(MaintenanceWriteLockMiddleware)

    async def fake_active_lock():
        return SimpleNamespace(reason="readable backup")

    monkeypatch.setattr("bigrag.middleware.maintenance.active_lock", fake_active_lock)

    @app.post("/v1/collections")
    async def mutate():
        return {"ok": True}

    @app.get("/v1/admin/backups")
    async def read():
        return {"ok": True}

    client = TestClient(app)

    assert client.post("/v1/collections").status_code == 423
    assert client.get("/v1/admin/backups").status_code == 200
