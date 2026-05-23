from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from bigrag.db.models import ConnectorSource
from bigrag.services.connectors.types import RemoteConnectorFile

S3_PROVIDER = "s3"
S3_DEFAULT_REGION = "us-east-1"
S3_R2_REGION = "auto"


class S3ConnectorError(RuntimeError):
    pass


def clean_s3_prefix(prefix: str | None) -> str:
    return str(prefix or "").strip().lstrip("/")


def is_cloudflare_r2_endpoint(endpoint_url: str | None) -> bool:
    if not endpoint_url:
        return False
    value = endpoint_url.strip()
    if not value:
        return False
    parsed = urlsplit(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or "").lower().rstrip(".")
    return host == "r2.cloudflarestorage.com" or host.endswith(".r2.cloudflarestorage.com")


def normalize_s3_region(region: str | None, endpoint_url: str | None) -> str:
    if is_cloudflare_r2_endpoint(endpoint_url):
        return S3_R2_REGION
    value = str(region or S3_DEFAULT_REGION).strip()
    return value or S3_DEFAULT_REGION


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
    endpoint_url = config.get("endpoint_url") or None
    if not bucket:
        raise S3ConnectorError("S3 bucket is required")
    return {
        "bucket": bucket,
        "prefix": prefix,
        "region": normalize_s3_region(config.get("region"), endpoint_url),
        "endpoint_url": endpoint_url,
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
