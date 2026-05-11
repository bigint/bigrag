from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bigrag.services import backup as backup_module


class FakeS3Client:
    def __init__(self) -> None:
        self.list_calls: list[dict[str, Any]] = []
        self.upload_calls: list[tuple[Path, str, str]] = []
        self.raise_on_list: Exception | None = None

    def list_objects_v2(self, **kwargs):
        self.list_calls.append(kwargs)
        if self.raise_on_list is not None:
            raise self.raise_on_list
        return {"Contents": []}

    def upload_file(self, source, bucket, key):
        self.upload_calls.append((source, bucket, key))


def _values(**overrides):
    base = {
        "backup_s3_bucket": "my-bucket",
        "backup_s3_region": "us-east-1",
        "backup_s3_endpoint_url": "https://s3.example.com",
        "backup_s3_access_key_id": "AKIA",
        "backup_s3_secret_access_key": "secret",
        "backup_s3_prefix": "/some/prefix/",
        "backup_s3_force_path_style": True,
    }
    base.update(overrides)
    return base


@pytest.fixture
def patch_boto(monkeypatch):
    fake = FakeS3Client()

    class FakeBoto3:
        def client(self, _service, **_kwargs):
            return fake

    class FakeConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    import sys
    import types

    boto3_mod = types.ModuleType("boto3")
    boto3_mod.client = lambda _service, **_kwargs: fake  # type: ignore[attr-defined]
    botocore_mod = types.ModuleType("botocore")
    config_mod = types.ModuleType("botocore.config")
    config_mod.Config = FakeConfig  # type: ignore[attr-defined]
    botocore_mod.config = config_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", boto3_mod)
    monkeypatch.setitem(sys.modules, "botocore", botocore_mod)
    monkeypatch.setitem(sys.modules, "botocore.config", config_mod)
    return fake


def test_s3_target_requires_bucket(patch_boto) -> None:
    with pytest.raises(backup_module.BackupConfigError, match="bucket is required"):
        backup_module.S3BackupTarget(_values(backup_s3_bucket=""))


def test_s3_target_strips_prefix_slashes(patch_boto) -> None:
    target = backup_module.S3BackupTarget(_values())
    assert target.prefix == "some/prefix"
    assert target.bucket == "my-bucket"
    assert target.region == "us-east-1"


def test_object_key_joins_prefix_and_path(patch_boto) -> None:
    target = backup_module.S3BackupTarget(_values())
    key = target.object_key("backups/abc", "/manifest.json")
    assert key == "backups/abc/manifest.json"


@pytest.mark.anyio
async def test_target_probe_runs_list(patch_boto) -> None:
    target = backup_module.S3BackupTarget(_values())
    await target.probe()
    assert patch_boto.list_calls
    assert patch_boto.list_calls[0]["Bucket"] == "my-bucket"
    assert patch_boto.list_calls[0]["Prefix"] == "some/prefix"


@pytest.mark.anyio
async def test_target_upload_file_records_object(patch_boto, tmp_path) -> None:
    target = backup_module.S3BackupTarget(_values())
    source = tmp_path / "obj.bin"
    source.write_bytes(b"hello")

    result = await target.upload_file(source, backup_prefix="bk/123", path="obj.bin")

    assert result.bytes == 5
    assert result.path == "obj.bin"
    assert patch_boto.upload_calls[0][2] == "bk/123/obj.bin"


@pytest.mark.anyio
async def test_test_backup_target_probes(patch_boto) -> None:
    await backup_module.test_backup_target(_values())
    assert patch_boto.list_calls


def test_backup_upload_stats_tracks_total_bytes() -> None:
    stats = backup_module.BackupUploadStats()
    stats.add(backup_module.UploadedObject(key="k", path="p", bytes=10, sha256="a"))
    stats.add(backup_module.UploadedObject(key="k2", path="p2", bytes=15, sha256="b"))
    assert stats.bytes == 25
    assert stats.object_count == 2


def test_readable_value_handles_primitives_and_complex_types() -> None:
    rv = backup_module._readable_value
    uid = uuid.uuid4()
    assert rv(None) is None
    assert rv(5) == 5
    assert rv(3.14) == 3.14
    assert rv(True) is True
    assert rv("hello") == "hello"
    assert rv(uid) == str(uid)
    assert rv(datetime(2026, 5, 9, tzinfo=UTC)).startswith("2026-05-09")
    assert rv(date(2026, 5, 9)) == "2026-05-09"
    assert rv(b"abc") == base64.b64encode(b"abc").decode("ascii")
    assert rv([1, "a", uid]) == [1, "a", str(uid)]
    assert rv({1: "v", "k": uid}) == {"1": "v", "k": str(uid)}


def test_file_stats_returns_size_and_digest(tmp_path) -> None:
    payload = b"hello world"
    target = tmp_path / "file.bin"
    target.write_bytes(payload)

    size, digest = backup_module._file_stats(target)

    assert size == len(payload)
    assert digest == hashlib.sha256(payload).hexdigest()


def test_backup_prefix_joins_parts() -> None:
    job_id = uuid.uuid4()
    assert backup_module._backup_prefix("base", job_id) == f"base/backups/{job_id}"
    assert backup_module._backup_prefix("", job_id) == f"backups/{job_id}"


def test_redact_column_returns_true_for_sensitive_names() -> None:
    column = SimpleNamespace(name="api_key", type=SimpleNamespace())
    assert backup_module._redact_column(SimpleNamespace(), column) is True


def test_redact_column_returns_true_for_encrypted_string() -> None:
    encrypted_type = type("EncryptedString", (), {})()
    column = SimpleNamespace(name="value", type=encrypted_type)
    assert backup_module._redact_column(SimpleNamespace(), column) is True


def test_redact_column_returns_false_for_plain_column() -> None:
    column = SimpleNamespace(name="name", type=SimpleNamespace())
    assert backup_module._redact_column(SimpleNamespace(), column) is False


def test_point_payload_handles_dict_and_object() -> None:
    point_dict = {"id": "p1", "payload": {"x": 1}, "vector": [0.1, 0.2]}
    payload_dict = backup_module._point_payload(point_dict)
    assert payload_dict["id"] == "p1"
    assert payload_dict["payload"] == {"x": 1}

    point_obj = SimpleNamespace(id="p2", payload={"y": 2}, vector=None)
    payload_obj = backup_module._point_payload(point_obj)
    assert payload_obj["id"] == "p2"
    assert payload_obj["vector"] is None


def test_write_json_writes_indented_payload(tmp_path) -> None:
    target = tmp_path / "out" / "file.json"
    backup_module._write_json(target, {"a": 1, "b": [1, 2]})
    text = target.read_text()
    assert '"a"' in text
    assert text.endswith("\n")


def test_write_schema_emits_sql(tmp_path) -> None:
    target = tmp_path / "schema.sql"
    backup_module._write_schema(target)
    contents = target.read_text()
    assert "CREATE TABLE" in contents
    assert "users" in contents


def test_manifest_includes_expected_keys() -> None:
    job_id = uuid.uuid4()
    target = SimpleNamespace(
        bucket="b",
        endpoint_url="https://s3",
        region="us-east-1",
        prefix="p",
    )
    stats = backup_module.BackupUploadStats()
    stats.add(backup_module.UploadedObject(key="k", path="p", bytes=5, sha256="h"))

    manifest = backup_module._manifest(
        job_id=job_id,
        target=target,
        backup_prefix="bk/job",
        table_counts={"users": 3},
        vector_counts={"docs": 12},
        upload_count=4,
        stats=stats,
    )

    assert manifest["backup_id"] == str(job_id)
    assert manifest["tables"] == {"users": 3}
    assert manifest["uploads"]["files"] == 4
    assert manifest["object_count"] == 1
    assert manifest["byte_count"] == 5
    assert manifest["destination"]["bucket"] == "b"
