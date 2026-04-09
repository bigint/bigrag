"""S3 connection helpers and object listing."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bigrag.logging import get_logger

logger = get_logger("bigrag.s3_client")

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".md", ".txt",
    ".csv", ".tsv", ".xml", ".json", ".png", ".jpg", ".jpeg", ".tiff",
    ".bmp", ".gif",
}


def build_s3_kwargs(job: dict) -> dict[str, Any]:
    """Build aiobotocore client kwargs from a job row."""
    from botocore import UNSIGNED
    from botocore.config import Config

    kwargs: dict[str, Any] = {"region_name": job["region"]}
    if job["endpoint_url"]:
        kwargs["endpoint_url"] = job["endpoint_url"]
    if job["no_sign_request"]:
        kwargs["config"] = Config(signature_version=UNSIGNED)
    elif job["access_key"] and job["secret_key"]:
        kwargs["aws_access_key_id"] = job["access_key"]
        kwargs["aws_secret_access_key"] = job["secret_key"]
    return kwargs


async def resolve_bucket_region(bucket: str) -> str | None:
    """Detect the actual region for a bucket.

    Tries GetBucketLocation first, then falls back to a HEAD request.
    Returns None if detection fails.
    """
    import aiobotocore.session
    from botocore import UNSIGNED
    from botocore.config import Config

    session = aiobotocore.session.get_session()

    # Try GetBucketLocation first
    try:
        kw: dict[str, Any] = {
            "region_name": "us-east-1",
            "config": Config(signature_version=UNSIGNED),
        }
        async with session.create_client("s3", **kw) as s3:
            r = await asyncio.wait_for(
                s3.get_bucket_location(Bucket=bucket), timeout=15,
            )
            return r.get("LocationConstraint") or "us-east-1"
    except Exception:
        pass

    # Fallback: HEAD request — region is in the response header
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as http:
            r = await http.head(f"https://{bucket}.s3.amazonaws.com")
            region = r.headers.get("x-amz-bucket-region")
            if region:
                logger.info("resolved region from HEAD", region=region)
                return region
    except Exception:
        pass

    logger.warning("could not detect region, using user-supplied")
    return None


async def list_s3_objects(
    bucket: str,
    prefix: str,
    s3_kwargs: dict[str, Any],
    extensions: set[str],
    on_progress: Callable[[int], Any] | None = None,
) -> list[dict]:
    """List and filter objects in an S3 bucket with automatic credential/region fallback.

    *on_progress* is called every 5 pages with the current object count.
    """
    import aiobotocore.session
    from botocore import UNSIGNED
    from botocore.config import Config
    from botocore.exceptions import NoCredentialsError

    session = aiobotocore.session.get_session()
    objects: list[dict] = []

    async def _list(kwargs: dict[str, Any]) -> None:
        pages = 0
        async with session.create_client("s3", **kwargs) as s3:
            paginator = s3.get_paginator("list_objects_v2")
            list_kw: dict[str, Any] = {"Bucket": bucket}
            if prefix:
                list_kw["Prefix"] = prefix
            async for page in paginator.paginate(**list_kw):
                pages += 1
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if key.endswith("/"):
                        continue
                    ext = Path(key).suffix.lower()
                    if ext in extensions:
                        objects.append(obj)
                if pages % 5 == 0 and on_progress:
                    on_progress(len(objects))

    def _is_redirect(exc: Exception) -> bool:
        s = str(exc)
        return "PermanentRedirect" in s or "specified endpoint" in s

    # 1. Try as-is
    try:
        await _list(s3_kwargs)
        return objects
    except NoCredentialsError:
        logger.info("no credentials, switching to unsigned")
        s3_kwargs["config"] = Config(signature_version=UNSIGNED)
    except Exception as e:
        if not _is_redirect(e):
            raise
        if "config" not in s3_kwargs:
            s3_kwargs["config"] = Config(signature_version=UNSIGNED)

    # 2. Try to detect correct region before listing
    region = await resolve_bucket_region(bucket)
    if region and region != s3_kwargs.get("region_name"):
        logger.info("detected region", actual=region)
        s3_kwargs["region_name"] = region
        s3_kwargs.pop("endpoint_url", None)

    # 3. List with resolved config
    logger.info(
        "listing with resolved config",
        region=s3_kwargs.get("region_name"),
        unsigned=True,
    )
    await _list(s3_kwargs)
    return objects


