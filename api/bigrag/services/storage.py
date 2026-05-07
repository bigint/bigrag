from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from bigrag.logging import get_logger
from bigrag.services import runtime_settings

logger = get_logger("bigrag.storage")


class StorageBackend(ABC):
    @abstractmethod
    async def put(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    async def get(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def delete_prefix(self, prefix: str) -> int: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def close(self) -> None: ...


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, key: str) -> Path:

        resolved = (self._base / key).resolve()
        if resolved != self._base and self._base not in resolved.parents:
            raise ValueError(f"Invalid storage key: {key}")
        return resolved

    async def put(self, key: str, data: bytes) -> None:
        path = self._safe_path(key)

        def _write():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(_write)
        logger.info("local put", key=key, size=len(data))

    async def get(self, key: str) -> bytes:
        path = self._safe_path(key)

        def _read():
            if not path.exists():
                raise FileNotFoundError(f"File not found: {key}")
            return path.read_bytes()

        data = await asyncio.to_thread(_read)
        logger.info("local get", key=key, size=len(data))
        return data

    async def delete(self, key: str) -> None:
        path = self._safe_path(key)

        def _delete():
            if path.exists():
                path.unlink()

        await asyncio.to_thread(_delete)
        logger.info("local delete", key=key)

    async def delete_prefix(self, prefix: str) -> int:
        import shutil

        target = self._safe_path(prefix)

        def _delete_prefix():
            if not target.exists():
                return 0
            if target.is_dir():
                count = sum(1 for _ in target.rglob("*") if _.is_file())
                shutil.rmtree(target, ignore_errors=True)
                return count
            target.unlink()
            return 1

        count = await asyncio.to_thread(_delete_prefix)
        if count:
            logger.info("local delete_prefix", prefix=prefix, count=count)
        return count

    async def exists(self, key: str) -> bool:
        path = self._safe_path(key)
        return await asyncio.to_thread(path.exists)

    async def close(self) -> None:
        pass


class S3Storage(StorageBackend):
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None,
        region: str,
        prefix: str,
        access_key_id: str | None,
        secret_access_key: str | None,
        force_path_style: bool,
    ) -> None:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("boto3 is required for S3 storage") from exc
        if not bucket:
            raise ValueError("S3 bucket is required")
        addressing_style = "path" if force_path_style else "auto"
        kwargs: dict[str, Any] = {
            "endpoint_url": endpoint_url,
            "region_name": region or "us-east-1",
            "config": Config(s3={"addressing_style": addressing_style}),
        }
        if access_key_id and secret_access_key:
            kwargs["aws_access_key_id"] = access_key_id
            kwargs["aws_secret_access_key"] = secret_access_key
        self._client = boto3.client("s3", **kwargs)
        self._bucket = bucket
        self._prefix = prefix.strip("/")

    def _key(self, key: str) -> str:
        clean = key.lstrip("/")
        if not clean or clean == "." or clean.startswith("../") or "/../" in clean:
            raise ValueError(f"Invalid storage key: {key}")
        return f"{self._prefix}/{clean}" if self._prefix else clean

    async def put(self, key: str, data: bytes) -> None:
        object_key = self._key(key)
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=object_key,
            Body=data,
        )
        logger.info("s3 put", key=object_key, size=len(data))

    async def get(self, key: str) -> bytes:
        object_key = self._key(key)

        def _read() -> bytes:
            response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            return response["Body"].read()

        data = await asyncio.to_thread(_read)
        logger.info("s3 get", key=object_key, size=len(data))
        return data

    async def delete(self, key: str) -> None:
        object_key = self._key(key)
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=object_key)
        logger.info("s3 delete", key=object_key)

    async def delete_prefix(self, prefix: str) -> int:
        object_prefix = self._key(prefix).rstrip("/") + "/"

        def _delete() -> int:
            count = 0
            for keys in self._list_keys(object_prefix):
                objects = [{"Key": key} for key in keys]
                if objects:
                    self._client.delete_objects(Bucket=self._bucket, Delete={"Objects": objects})
                    count += len(objects)
            return count

        count = await asyncio.to_thread(_delete)
        if count:
            logger.info("s3 delete_prefix", prefix=object_prefix, count=count)
        return count

    def _list_keys(self, prefix: str) -> Iterator[list[str]]:
        token: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "Bucket": self._bucket,
                "Prefix": prefix,
                "MaxKeys": 1000,
            }
            if token:
                kwargs["ContinuationToken"] = token
            response = self._client.list_objects_v2(**kwargs)
            keys = [item["Key"] for item in response.get("Contents", [])]
            if keys:
                yield keys
            if not response.get("IsTruncated"):
                return
            token = response.get("NextContinuationToken")

    async def exists(self, key: str) -> bool:
        object_key = self._key(key)

        def _exists() -> bool:
            try:
                self._client.head_object(Bucket=self._bucket, Key=object_key)
                return True
            except Exception as exc:
                code = getattr(getattr(exc, "response", None), "get", lambda *_: {})(
                    "Error", {}
                ).get("Code")
                if code in {"404", "NoSuchKey", "NotFound"}:
                    return False
                raise

        return await asyncio.to_thread(_exists)

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            await asyncio.to_thread(close)


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    if _storage is None:
        raise RuntimeError("Storage backend not initialized")
    return _storage


def init_storage(upload_dir: str = "./data/uploads") -> StorageBackend:
    global _storage

    _storage = LocalStorage(upload_dir)
    logger.info("local storage initialized", upload_dir=upload_dir)

    return _storage


async def init_storage_from_runtime(upload_dir: str = "./data/uploads") -> StorageBackend:
    values = await runtime_settings.all_runtime_values()
    return init_storage_from_values(upload_dir, values)


def init_storage_from_values(upload_dir: str, values: dict[str, Any]) -> StorageBackend:
    global _storage

    _storage = build_storage_from_values(upload_dir, values)
    if isinstance(_storage, LocalStorage):
        logger.info("local storage initialized", upload_dir=upload_dir)
    else:
        logger.info("s3 storage initialized", bucket=values.get("storage_s3_bucket"))
    return _storage


def build_storage_from_values(upload_dir: str, values: dict[str, Any]) -> StorageBackend:
    backend = values.get("storage_backend") or "local"
    if backend == "local":
        return LocalStorage(upload_dir)
    if backend != "s3":
        raise ValueError(f"Unsupported storage backend: {backend}")
    return S3Storage(
        bucket=values.get("storage_s3_bucket") or "",
        endpoint_url=values.get("storage_s3_endpoint_url"),
        region=values.get("storage_s3_region") or "us-east-1",
        prefix=values.get("storage_s3_prefix") or "",
        access_key_id=values.get("storage_s3_access_key_id"),
        secret_access_key=values.get("storage_s3_secret_access_key"),
        force_path_style=bool(values.get("storage_s3_force_path_style")),
    )
