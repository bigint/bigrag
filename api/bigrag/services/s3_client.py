"""S3 connection helpers and object listing."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
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

    from botocore.exceptions import BotoCoreError, ClientError

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
    except (BotoCoreError, ClientError, TimeoutError) as exc:
        logger.debug(
            "GetBucketLocation failed, falling back to HEAD",
            bucket=bucket,
            error=f"{exc.__class__.__name__}: {exc}",
        )

    # Fallback: HEAD request — region is in the response header
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as http:
            r = await http.head(f"https://{bucket}.s3.amazonaws.com")
            region = r.headers.get("x-amz-bucket-region")
            if region:
                logger.info("resolved region from HEAD", region=region)
                return region
    except (httpx.HTTPError, OSError) as exc:
        logger.debug(
            "HEAD bucket region probe failed",
            bucket=bucket,
            error=f"{exc.__class__.__name__}: {exc}",
        )

    logger.warning("could not detect region, using user-supplied")
    return None


async def resolve_s3_config(
    bucket: str,
    prefix: str,
    s3_kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Test S3 access and resolve correct credentials/region via fallback.

    Returns the (possibly modified) *s3_kwargs* that successfully listed.
    """
    import aiobotocore.session
    from botocore import UNSIGNED
    from botocore.config import Config
    from botocore.exceptions import NoCredentialsError

    session = aiobotocore.session.get_session()

    async def _probe(kwargs: dict[str, Any]) -> None:
        async with session.create_client("s3", **kwargs) as s3:
            list_kw: dict[str, Any] = {"Bucket": bucket, "MaxKeys": 1}
            if prefix:
                list_kw["Prefix"] = prefix
            await s3.list_objects_v2(**list_kw)

    def _is_redirect(exc: Exception) -> bool:
        s = str(exc)
        return "PermanentRedirect" in s or "specified endpoint" in s

    # 1. Try as-is
    try:
        await _probe(s3_kwargs)
        return s3_kwargs
    except NoCredentialsError:
        logger.info("no credentials, switching to unsigned")
        s3_kwargs["config"] = Config(signature_version=UNSIGNED)
    except Exception as e:
        if not _is_redirect(e):
            raise
        if "config" not in s3_kwargs:
            s3_kwargs["config"] = Config(signature_version=UNSIGNED)

    # 2. Try to detect correct region
    region = await resolve_bucket_region(bucket)
    if region and region != s3_kwargs.get("region_name"):
        logger.info("detected region", actual=region)
        s3_kwargs["region_name"] = region
        s3_kwargs.pop("endpoint_url", None)

    # 3. Verify resolved config works
    logger.info(
        "resolved s3 config",
        region=s3_kwargs.get("region_name"),
        unsigned=True,
    )
    await _probe(s3_kwargs)
    return s3_kwargs


async def iter_s3_pages(
    bucket: str,
    prefix: str,
    s3_kwargs: dict[str, Any],
    extensions: set[str],
    on_progress: Callable[[int], Any] | None = None,
) -> AsyncIterator[list[dict]]:
    """Yield pages of filtered S3 objects.

    Each page contains up to 1000 objects (S3 default) filtered by extension.
    *on_progress* is called every 5 pages with the running total.
    """
    import aiobotocore.session

    session = aiobotocore.session.get_session()
    total = 0
    pages = 0

    async with session.create_client("s3", **s3_kwargs) as s3:
        paginator = s3.get_paginator("list_objects_v2")
        list_kw: dict[str, Any] = {"Bucket": bucket}
        if prefix:
            list_kw["Prefix"] = prefix
        async for page in paginator.paginate(**list_kw):
            pages += 1
            filtered: list[dict] = []
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/"):
                    continue
                if Path(key).suffix.lower() in extensions:
                    filtered.append(obj)
            total += len(filtered)
            if pages % 5 == 0 and on_progress:
                on_progress(total)
            if filtered:
                yield filtered


