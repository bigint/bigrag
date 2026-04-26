from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path

from bigrag.logging import get_logger

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
        """Resolve key to a path guaranteed to be under base directory."""
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
        logger.info(f"local put: key={key} size={len(data)}")

    async def get(self, key: str) -> bytes:
        path = self._safe_path(key)

        def _read():
            if not path.exists():
                raise FileNotFoundError(f"File not found: {key}")
            return path.read_bytes()

        data = await asyncio.to_thread(_read)
        logger.info(f"local get: key={key} size={len(data)}")
        return data

    async def delete(self, key: str) -> None:
        path = self._safe_path(key)

        def _delete():
            if path.exists():
                path.unlink()

        await asyncio.to_thread(_delete)
        logger.info(f"local delete: key={key}")

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
            logger.info(f"local delete_prefix: prefix={prefix} count={count}")
        return count

    async def exists(self, key: str) -> bool:
        path = self._safe_path(key)
        return await asyncio.to_thread(path.exists)

    async def close(self) -> None:
        pass


class S3Storage(StorageBackend):
    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None = None,
        region: str = "us-east-1",
        access_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        try:
            from aiobotocore.session import get_session
        except ImportError as e:
            raise ImportError(
                "aiobotocore is required for S3 storage. Install it with: pip install 'bigrag[s3]'"
            ) from e
        self._bucket = bucket
        self._session = get_session()
        self._config = {
            "region_name": region,
        }
        if endpoint_url:
            self._config["endpoint_url"] = endpoint_url
        if access_key and secret_key:
            self._config["aws_access_key_id"] = access_key
            self._config["aws_secret_access_key"] = secret_key
        self._client_ctx = None
        self._client = None

    async def _get_client(self):
        if self._client is None:
            self._client_ctx = self._session.create_client("s3", **self._config)
            self._client = await self._client_ctx.__aenter__()
        return self._client

    async def put(self, key: str, data: bytes) -> None:
        client = await self._get_client()
        await client.put_object(Bucket=self._bucket, Key=key, Body=data)
        logger.info(f"s3 put: bucket={self._bucket} key={key} size={len(data)}")

    async def get(self, key: str) -> bytes:
        client = await self._get_client()
        resp = await client.get_object(Bucket=self._bucket, Key=key)
        async with resp["Body"] as stream:
            data = await stream.read()
        logger.info(f"s3 get: bucket={self._bucket} key={key} size={len(data)}")
        return data

    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete_object(Bucket=self._bucket, Key=key)
        logger.info(f"s3 delete: bucket={self._bucket} key={key}")

    async def delete_prefix(self, prefix: str) -> int:
        client = await self._get_client()
        count = 0
        paginator = client.get_paginator("list_objects_v2")
        async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            objects = page.get("Contents", [])
            if not objects:
                continue
            delete_req = {"Objects": [{"Key": obj["Key"]} for obj in objects]}
            await client.delete_objects(Bucket=self._bucket, Delete=delete_req)
            count += len(objects)
        logger.info(f"s3 delete_prefix: bucket={self._bucket} prefix={prefix} count={count}")
        return count

    async def exists(self, key: str) -> bool:
        client = await self._get_client()
        try:
            await client.head_object(Bucket=self._bucket, Key=key)
            return True
        except client.exceptions.ClientError:
            return False

    async def close(self) -> None:
        if self._client_ctx:
            await self._client_ctx.__aexit__(None, None, None)
            self._client = None
            self._client_ctx = None


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    if _storage is None:
        raise RuntimeError("Storage backend not initialized")
    return _storage


def init_storage(
    backend: str = "local",
    upload_dir: str = "./data/uploads",
    s3_bucket: str | None = None,
    s3_endpoint_url: str | None = None,
    s3_region: str = "us-east-1",
    s3_access_key: str | None = None,
    s3_secret_key: str | None = None,
) -> StorageBackend:
    global _storage

    if backend == "s3":
        if not s3_bucket:
            raise ValueError("S3 bucket name is required when using S3 storage")
        _storage = S3Storage(
            bucket=s3_bucket,
            endpoint_url=s3_endpoint_url,
            region=s3_region,
            access_key=s3_access_key,
            secret_key=s3_secret_key,
        )
        logger.info(
            f"S3 storage initialized bucket={s3_bucket} endpoint={s3_endpoint_url or 'AWS'}"
        )
    else:
        _storage = LocalStorage(upload_dir)
        logger.info(f"Local storage initialized dir={upload_dir}")

    return _storage
