from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .filesystem import _file_stats


@dataclass
class UploadedObject:
    key: str
    path: str
    bytes: int
    sha256: str


@dataclass
class BackupUploadStats:
    object_count: int = 0
    byte_count: int = 0

    @property
    def bytes(self) -> int:
        return self.byte_count

    def add(self, obj: UploadedObject) -> None:
        self.object_count += 1
        self.byte_count += obj.bytes


class BackupConfigError(RuntimeError):
    pass


class S3BackupTarget:
    def __init__(self, values: dict[str, Any]) -> None:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise BackupConfigError("boto3 is required for S3-compatible backups") from exc
        bucket = values.get("backup_s3_bucket") or ""
        if not bucket:
            raise BackupConfigError("backup_s3_bucket is required")
        force_path_style = bool(values.get("backup_s3_force_path_style"))
        kwargs: dict[str, Any] = {
            "endpoint_url": values.get("backup_s3_endpoint_url"),
            "region_name": values.get("backup_s3_region") or "us-east-1",
            "config": Config(s3={"addressing_style": "path" if force_path_style else "auto"}),
        }
        access_key_id = values.get("backup_s3_access_key_id")
        secret_access_key = values.get("backup_s3_secret_access_key")
        if access_key_id and secret_access_key:
            kwargs["aws_access_key_id"] = access_key_id
            kwargs["aws_secret_access_key"] = secret_access_key
        self.client = boto3.client("s3", **kwargs)
        self.bucket = bucket
        self.endpoint_url = values.get("backup_s3_endpoint_url")
        self.region = values.get("backup_s3_region") or "us-east-1"
        self.prefix = str(values.get("backup_s3_prefix") or "").strip("/")

    def object_key(self, backup_prefix: str, path: str) -> str:
        clean = path.lstrip("/")
        return f"{backup_prefix}/{clean}"

    async def probe(self) -> None:
        await asyncio.to_thread(
            self.client.list_objects_v2,
            Bucket=self.bucket,
            Prefix=self.prefix,
            MaxKeys=1,
        )

    async def upload_file(self, source: Path, *, backup_prefix: str, path: str) -> UploadedObject:
        object_key = self.object_key(backup_prefix, path)
        size, digest = await asyncio.to_thread(_file_stats, source)
        await asyncio.to_thread(
            self.client.upload_file,
            str(source),
            self.bucket,
            object_key,
            ExtraArgs={"ServerSideEncryption": "AES256"},
        )
        return UploadedObject(key=object_key, path=path, bytes=size, sha256=digest)


def build_backup_target(values: dict[str, Any]) -> S3BackupTarget:
    return S3BackupTarget(values)


async def test_backup_target(values: dict[str, Any]) -> None:
    target = build_backup_target(values)
    await target.probe()
