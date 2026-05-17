from __future__ import annotations

import asyncio
import io
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any, BinaryIO

from bigrag.logging import get_logger
from bigrag.services.storage._key_validation import validate_storage_key
from bigrag.services.storage.base import StorageBackend

logger = get_logger("bigrag.storage")


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
            from boto3.s3.transfer import TransferConfig
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
        self._transfer_config = TransferConfig(
            multipart_threshold=8 * 1024 * 1024,
            multipart_chunksize=8 * 1024 * 1024,
            max_concurrency=4,
            use_threads=True,
        )

    def _key(self, key: str) -> str:
        clean = validate_storage_key(key)
        return f"{self._prefix}/{clean}" if self._prefix else clean

    async def put(self, key: str, data: bytes) -> None:
        await self.put_stream(key, io.BytesIO(data), size=len(data))

    async def put_stream(self, key: str, fileobj: BinaryIO, size: int | None = None) -> None:
        object_key = self._key(key)
        await asyncio.to_thread(
            self._client.upload_fileobj,
            fileobj,
            self._bucket,
            object_key,
            Config=self._transfer_config,
        )
        logger.info("s3 put", key=object_key, size=size if size is not None else -1)

    async def get(self, key: str) -> bytes:
        object_key = self._key(key)

        def _read() -> bytes:
            response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            return response["Body"].read()

        data = await asyncio.to_thread(_read)
        logger.info("s3 get", key=object_key, size=len(data))
        return data

    async def get_stream(self, key: str, chunk_size: int = 65536) -> AsyncIterator[bytes]:
        object_key = self._key(key)

        def _open():
            response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            return response["Body"]

        body = await asyncio.to_thread(_open)
        try:
            while True:
                chunk = await asyncio.to_thread(body.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            close = getattr(body, "close", None)
            if close is not None:
                await asyncio.to_thread(close)

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

    async def write_to_path(self, key: str, path: Path) -> int:
        object_key = self._key(key)

        def _write() -> int:
            path.parent.mkdir(parents=True, exist_ok=True)
            response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            size = 0
            with path.open("wb") as out:
                for chunk in response["Body"].iter_chunks(chunk_size=1024 * 1024):
                    if chunk:
                        out.write(chunk)
                        size += len(chunk)
            return size

        size = await asyncio.to_thread(_write)
        logger.info(f"s3 write_to_path: key={object_key} size={size}")
        return size

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is not None:
            await asyncio.to_thread(close)
