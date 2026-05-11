from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from rag_computer.services import storage


class FakeBody:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def read(self) -> bytes:
        return self.data

    def iter_chunks(self, chunk_size: int):
        assert chunk_size > 0
        yield self.data[:2]
        yield b""
        yield self.data[2:]


class MissingObjectError(Exception):
    def __init__(self) -> None:
        self.response = {"Error": {"Code": "404"}}


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted = []
        self.closed = False
        self.pages = []

    def put_object(self, **kwargs):
        self.objects[kwargs["Key"]] = kwargs["Body"]

    def get_object(self, **kwargs):
        return {"Body": FakeBody(self.objects[kwargs["Key"]])}

    def delete_object(self, **kwargs):
        self.deleted.append(kwargs["Key"])
        self.objects.pop(kwargs["Key"], None)

    def delete_objects(self, **kwargs):
        for item in kwargs["Delete"]["Objects"]:
            self.deleted.append(item["Key"])
            self.objects.pop(item["Key"], None)

    def list_objects_v2(self, **kwargs):
        if self.pages:
            return self.pages.pop(0)
        prefix = kwargs["Prefix"]
        return {
            "Contents": [{"Key": key} for key in self.objects if key.startswith(prefix)],
            "IsTruncated": False,
        }

    def head_object(self, **kwargs):
        if kwargs["Key"] not in self.objects:
            raise MissingObjectError()

    def close(self):
        self.closed = True


def s3_backend(client: FakeS3Client | None = None) -> storage.S3Storage:
    backend = object.__new__(storage.S3Storage)
    backend._client = client or FakeS3Client()
    backend._bucket = "bucket"
    backend._prefix = "prefix"
    return backend


def test_local_storage_roundtrip_delete_prefix_and_path_safety(tmp_path: Path) -> None:
    async def run() -> None:
        backend = storage.LocalStorage(str(tmp_path / "uploads"))
        await backend.put("docs/a.txt", b"hello")

        assert await backend.get("docs/a.txt") == b"hello"
        assert await backend.exists("docs/a.txt") is True

        target = tmp_path / "copy" / "a.txt"
        assert await backend.write_to_path("docs/a.txt", target) == 5
        assert target.read_bytes() == b"hello"

        await backend.put("docs/nested/b.txt", b"world")
        assert await backend.delete_prefix("docs") == 2
        assert await backend.exists("docs/a.txt") is False
        assert await backend.delete_prefix("docs") == 0

        with pytest.raises(ValueError):
            await backend.put("../escape.txt", b"bad")
        with pytest.raises(FileNotFoundError):
            await backend.get("missing.txt")

    asyncio.run(run())


def test_s3_storage_maps_keys_and_object_operations(tmp_path: Path) -> None:
    async def run() -> None:
        client = FakeS3Client()
        backend = s3_backend(client)

        await backend.put("/docs/a.txt", b"hello")
        assert client.objects == {"prefix/docs/a.txt": b"hello"}
        assert await backend.get("docs/a.txt") == b"hello"
        assert await backend.exists("docs/a.txt") is True
        assert await backend.exists("docs/missing.txt") is False

        target = tmp_path / "out" / "a.txt"
        assert await backend.write_to_path("docs/a.txt", target) == 5
        assert target.read_bytes() == b"hello"

        await backend.delete("docs/a.txt")
        assert client.deleted == ["prefix/docs/a.txt"]
        await backend.close()
        assert client.closed is True

    asyncio.run(run())


def test_s3_delete_prefix_handles_pagination_and_invalid_keys() -> None:
    async def run() -> None:
        client = FakeS3Client()
        client.objects = {
            "prefix/docs/a.txt": b"a",
            "prefix/docs/b.txt": b"b",
            "prefix/other/c.txt": b"c",
        }
        client.pages = [
            {
                "Contents": [{"Key": "prefix/docs/a.txt"}],
                "IsTruncated": True,
                "NextContinuationToken": "next",
            },
            {
                "Contents": [{"Key": "prefix/docs/b.txt"}],
                "IsTruncated": False,
            },
        ]
        backend = s3_backend(client)

        assert await backend.delete_prefix("docs") == 2
        assert sorted(client.objects) == ["prefix/other/c.txt"]

        with pytest.raises(ValueError):
            backend._key("../bad")
        with pytest.raises(ValueError):
            backend._key("a/../bad")

    asyncio.run(run())


def test_build_storage_from_values_selects_backend(monkeypatch, tmp_path: Path) -> None:
    class FakeBoto3:
        def client(self, service, **kwargs):
            assert service == "s3"
            return FakeS3Client()

    class FakeConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    monkeypatch.setitem(__import__("sys").modules, "boto3", FakeBoto3())
    monkeypatch.setitem(
        __import__("sys").modules,
        "botocore.config",
        type("FakeConfigModule", (), {"Config": FakeConfig}),
    )

    local = storage.build_storage_from_values(str(tmp_path), {"storage_backend": "local"})
    assert isinstance(local, storage.LocalStorage)

    s3 = storage.build_storage_from_values(
        str(tmp_path),
        {
            "storage_backend": "s3",
            "storage_s3_bucket": "bucket",
            "storage_s3_region": "us-west-2",
            "storage_s3_prefix": "uploads",
            "storage_s3_access_key_id": "id",
            "storage_s3_secret_access_key": "secret",
            "storage_s3_force_path_style": True,
        },
    )
    assert isinstance(s3, storage.S3Storage)

    with pytest.raises(ValueError):
        storage.build_storage_from_values(str(tmp_path), {"storage_backend": "unknown"})
    with pytest.raises(RuntimeError):
        storage._storage = None
        storage.get_storage()
