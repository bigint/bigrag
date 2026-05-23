from __future__ import annotations

from typing import Any

from bigrag.db.models import ConnectorSource
from bigrag.services.connectors.types import RemoteConnectorFile

S3_PROVIDER = "s3"
S3_DEFAULT_REGION = "us-east-1"


class S3ConnectorError(RuntimeError):
    pass


def clean_s3_prefix(prefix: str | None) -> str:
    return str(prefix or "").strip().lstrip("/")


def s3_root_id(bucket: str, prefix: str) -> str:
    return f"{bucket}/{prefix}" if prefix else bucket


def s3_root_name(bucket: str, prefix: str) -> str:
    return f"s3://{bucket}/{prefix}" if prefix else f"s3://{bucket}"


def s3_metadata(
    *,
    bucket: str,
    prefix: str,
    region: str,
    endpoint_url: str | None,
    force_path_style: bool,
    user_metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "s3": {
            "bucket": bucket,
            "prefix": prefix,
            "region": region,
            "endpoint_url": endpoint_url,
            "force_path_style": force_path_style,
            "has_credentials": True,
        },
        "user_metadata": dict(user_metadata or {}),
    }


def source_s3_config(source: ConnectorSource) -> dict[str, Any]:
    config = dict((source.meta or {}).get("s3") or {})
    bucket = str(config.get("bucket") or "").strip()
    prefix = clean_s3_prefix(config.get("prefix"))
    if not bucket:
        raise S3ConnectorError("S3 bucket is required")
    return {
        "bucket": bucket,
        "prefix": prefix,
        "region": str(config.get("region") or S3_DEFAULT_REGION).strip() or S3_DEFAULT_REGION,
        "endpoint_url": config.get("endpoint_url") or None,
        "force_path_style": bool(config.get("force_path_style")),
    }


def s3_object_metadata(
    *,
    source: ConnectorSource,
    remote: RemoteConnectorFile,
) -> dict[str, Any]:
    config = source_s3_config(source)
    return {
        "source": "s3",
        "connector": S3_PROVIDER,
        "s3": {
            "bucket": config["bucket"],
            "prefix": config["prefix"],
            "key": remote.id.removeprefix(f"s3://{config['bucket']}/"),
            "etag": remote.version,
            "size": remote.size,
            "modified_time": remote.modified_time.isoformat() if remote.modified_time else None,
        },
    }
