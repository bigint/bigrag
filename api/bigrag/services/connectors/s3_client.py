from __future__ import annotations

import asyncio
import hashlib
import tempfile
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from bigrag.db.models import ConnectorSource, ConnectorSourceCredential
from bigrag.services.connectors.s3_types import S3ConnectorError, source_s3_config
from bigrag.services.connectors.types import DownloadedConnectorFile, RemoteConnectorFile
from bigrag.services.documents import SUPPORTED_EXTENSIONS

S3_CLIENT_CONNECT_TIMEOUT_SECONDS = 10
S3_CLIENT_READ_TIMEOUT_SECONDS = 60
S3_CLIENT_RETRY_ATTEMPTS = 3
S3_PROBE_CONNECT_TIMEOUT_SECONDS = 3
S3_PROBE_READ_TIMEOUT_SECONDS = 8
S3_PROBE_RETRY_ATTEMPTS = 1
S3_PROBE_TIMEOUT_SECONDS = 12


def _boto3_client(
    *,
    access_key_id: str,
    secret_access_key: str,
    session_token: str | None,
    region: str,
    endpoint_url: str | None,
    force_path_style: bool,
    connect_timeout: int = S3_CLIENT_CONNECT_TIMEOUT_SECONDS,
    read_timeout: int = S3_CLIENT_READ_TIMEOUT_SECONDS,
    retry_attempts: int = S3_CLIENT_RETRY_ATTEMPTS,
):
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise S3ConnectorError("boto3 is required for S3 connector sync") from exc
    kwargs: dict[str, Any] = {
        "aws_access_key_id": access_key_id,
        "aws_secret_access_key": secret_access_key,
        "aws_session_token": session_token,
        "endpoint_url": endpoint_url,
        "region_name": region,
        "config": Config(
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            retries={"max_attempts": retry_attempts, "mode": "standard"},
            s3={"addressing_style": "path" if force_path_style else "auto"},
        ),
    }
    return boto3.client("s3", **kwargs)


async def probe_s3_credentials(
    *,
    bucket: str,
    prefix: str,
    access_key_id: str,
    secret_access_key: str,
    session_token: str | None,
    region: str,
    endpoint_url: str | None,
    force_path_style: bool,
) -> None:
    client = _boto3_client(
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        session_token=session_token,
        region=region,
        endpoint_url=endpoint_url,
        force_path_style=force_path_style,
        connect_timeout=S3_PROBE_CONNECT_TIMEOUT_SECONDS,
        read_timeout=S3_PROBE_READ_TIMEOUT_SECONDS,
        retry_attempts=S3_PROBE_RETRY_ATTEMPTS,
    )
    try:
        await asyncio.wait_for(
            asyncio.to_thread(
                client.list_objects_v2,
                Bucket=bucket,
                Prefix=prefix,
                MaxKeys=1,
            ),
            timeout=S3_PROBE_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise S3ConnectorError("S3 bucket did not respond before timeout") from exc
    except Exception as exc:
        raise S3ConnectorError("S3 bucket could not be reached") from exc


async def list_s3_objects(session: Any, *, source: ConnectorSource) -> list[RemoteConnectorFile]:
    credential = await source_credential(session, source)
    config = source_s3_config(source)
    client = _client_from_credential(credential)
    bucket = config["bucket"]
    prefix = config["prefix"]
    try:
        return await asyncio.to_thread(_list_s3_objects_sync, client, bucket, prefix)
    except Exception as exc:
        raise S3ConnectorError("S3 objects could not be listed") from exc


async def download_s3_object(
    session: Any,
    *,
    source: ConnectorSource,
    remote: RemoteConnectorFile,
) -> DownloadedConnectorFile:
    credential = await source_credential(session, source)
    config = source_s3_config(source)
    client = _client_from_credential(credential)
    bucket = config["bucket"]
    key = _remote_key(bucket, remote)
    try:
        return await asyncio.to_thread(_download_s3_object_sync, client, bucket, key, remote)
    except Exception as exc:
        raise S3ConnectorError("S3 object could not be downloaded") from exc


async def source_credential(session: Any, source: ConnectorSource) -> ConnectorSourceCredential:
    credential = await session.scalar(
        sa.select(ConnectorSourceCredential).where(ConnectorSourceCredential.source_id == source.id)
    )
    if credential is None:
        raise S3ConnectorError("S3 source credentials are missing")
    return credential


def _client_from_credential(credential: ConnectorSourceCredential):
    return _boto3_client(
        access_key_id=credential.access_key_id,
        secret_access_key=credential.secret_access_key,
        session_token=credential.session_token,
        region=credential.region,
        endpoint_url=credential.endpoint_url,
        force_path_style=credential.force_path_style,
    )


def _list_s3_objects_sync(client, bucket: str, prefix: str) -> list[RemoteConnectorFile]:
    paginator = client.get_paginator("list_objects_v2")
    remotes: list[RemoteConnectorFile] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = str(item.get("Key") or "")
            if not key or (key.endswith("/") and int(item.get("Size") or 0) == 0):
                continue
            file_ext = Path(key).suffix.lower()
            if file_ext not in SUPPORTED_EXTENSIONS:
                continue
            etag = str(item.get("ETag") or "").strip('"') or None
            remotes.append(
                RemoteConnectorFile(
                    id=f"s3://{bucket}/{key}",
                    name=Path(key).name,
                    mime_type="application/octet-stream",
                    modified_time=item.get("LastModified"),
                    size=int(item.get("Size") or 0),
                    version=etag,
                    web_url=f"s3://{bucket}/{key}",
                )
            )
    return remotes


def _download_s3_object_sync(
    client,
    bucket: str,
    key: str,
    remote: RemoteConnectorFile,
) -> DownloadedConnectorFile:
    file_ext = Path(key).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        path = Path(tmp.name)
        hasher = hashlib.sha256()
        size = 0
        response = client.get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        try:
            while chunk := body.read(1024 * 1024):
                size += len(chunk)
                hasher.update(chunk)
                tmp.write(chunk)
        finally:
            body.close()
    return DownloadedConnectorFile(
        remote=remote,
        filename=Path(key).name,
        file_ext=file_ext,
        path=path,
        file_size=size,
        content_hash=hasher.hexdigest(),
    )


def _remote_key(bucket: str, remote: RemoteConnectorFile) -> str:
    prefix = f"s3://{bucket}/"
    if not remote.id.startswith(prefix):
        raise S3ConnectorError("S3 remote id does not match source bucket")
    return remote.id.removeprefix(prefix)
