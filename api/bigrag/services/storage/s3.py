from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, BinaryIO

from bigrag.logging import get_logger
from bigrag.services.storage.base import StorageBackend

logger = get_logger("bigrag.storage")

_LIST_PAGE_SIZE = 1000


class S3Storage(StorageBackend):
    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "",
        endpoint_url: str | None = None,
        region: str = "us-east-1",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        force_path_style: bool = False,
    ) -> None:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("boto3 is required for the s3 storage backend") from exc
        if not bucket:
            raise ValueError("storage_s3_bucket is required for the s3 storage backend")
        kwargs: dict[str, Any] = {
            "endpoint_url": endpoint_url,
            "region_name": region or "us-east-1",
            "config": Config(
                s3={"addressing_style": "path" if force_path_style else "auto"},
            ),
        }
        if access_key_id and secret_access_key:
            kwargs["aws_access_key_id"] = access_key_id
            kwargs["aws_secret_access_key"] = secret_access_key
        self._client = boto3.client("s3", **kwargs)
        self._bucket = bucket
        self._prefix = str(prefix or "").strip("/")

    def _object_key(self, key: str) -> str:
        clean = key.strip("/")
        if not clean or ".." in clean.split("/"):
            raise ValueError(f"Invalid storage key: {key}")
        return f"{self._prefix}/{clean}" if self._prefix else clean

    async def put(self, key: str, data: bytes) -> None:
        object_key = self._object_key(key)
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=object_key,
            Body=data,
        )
        logger.info("s3 put", key=key, size=len(data))

    async def put_stream(self, key: str, fileobj: BinaryIO, size: int | None = None) -> None:
        object_key = self._object_key(key)
        await asyncio.to_thread(
            self._client.upload_fileobj,
            fileobj,
            self._bucket,
            object_key,
        )
        logger.info("s3 put", key=key, size=size)

    async def get(self, key: str) -> bytes:
        object_key = self._object_key(key)

        def _read() -> bytes:
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            except self._client.exceptions.NoSuchKey as exc:
                raise FileNotFoundError(f"File not found: {key}") from exc
            return response["Body"].read()

        data = await asyncio.to_thread(_read)
        logger.info("s3 get", key=key, size=len(data))
        return data

    async def get_stream(self, key: str, chunk_size: int = 65536) -> AsyncIterator[bytes]:
        object_key = self._object_key(key)

        def _open() -> Any:
            try:
                response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            except self._client.exceptions.NoSuchKey as exc:
                raise FileNotFoundError(f"File not found: {key}") from exc
            return response["Body"]

        body = await asyncio.to_thread(_open)
        try:
            while True:
                chunk = await asyncio.to_thread(body.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(body.close)

    async def delete(self, key: str) -> None:
        object_key = self._object_key(key)
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self._bucket,
            Key=object_key,
        )
        logger.info("s3 delete", key=key)

    async def delete_prefix(self, prefix: str) -> int:
        object_prefix = self._object_key(prefix)

        def _delete_prefix() -> int:
            paginator = self._client.get_paginator("list_objects_v2")
            deleted = 0
            for page in paginator.paginate(Bucket=self._bucket, Prefix=object_prefix):
                contents = page.get("Contents") or []
                if not contents:
                    continue
                for start in range(0, len(contents), _LIST_PAGE_SIZE):
                    batch = contents[start : start + _LIST_PAGE_SIZE]
                    self._client.delete_objects(
                        Bucket=self._bucket,
                        Delete={"Objects": [{"Key": item["Key"]} for item in batch]},
                    )
                    deleted += len(batch)
            return deleted

        count = await asyncio.to_thread(_delete_prefix)
        if count:
            logger.info("s3 delete_prefix", prefix=prefix, count=count)
        return count

    async def exists(self, key: str) -> bool:
        object_key = self._object_key(key)

        def _exists() -> bool:
            try:
                self._client.head_object(Bucket=self._bucket, Key=object_key)
            except self._client.exceptions.ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code in {"404", "NoSuchKey", "NotFound"}:
                    return False
                raise
            return True

        return await asyncio.to_thread(_exists)

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)
