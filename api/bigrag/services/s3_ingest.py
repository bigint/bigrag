"""Persistent S3 ingest jobs that survive server restarts."""

from __future__ import annotations

import asyncio
import io
import tarfile
import uuid
from pathlib import Path
from typing import Any

from bigrag.logging import get_logger

logger = get_logger("bigrag.s3_ingest")

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".md", ".txt",
    ".csv", ".tsv", ".xml", ".json", ".png", ".jpg", ".jpeg", ".tiff",
    ".bmp", ".gif",
}
S3_INGESTABLE = SUPPORTED_EXTENSIONS | {".tar"}

_tasks: dict[str, asyncio.Task] = {}  # job_id → task


async def create_job(
    collection_id: str,
    collection_name: str,
    bucket: str,
    prefix: str,
    region: str,
    endpoint_url: str | None,
    access_key: str | None,
    secret_key: str | None,
    no_sign_request: bool,
    metadata: dict,
    file_types: list[str] | None = None,
) -> dict:
    """Create a persistent S3 ingest job and start processing."""
    from bigrag.database import db

    job_id = str(uuid.uuid4())
    row = await db.fetchrow(
        """
        INSERT INTO s3_ingest_jobs
            (id, collection_id, collection_name, bucket, prefix, region,
             endpoint_url, access_key, secret_key, no_sign_request, metadata,
             file_types)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        RETURNING *
        """,
        uuid.UUID(job_id),
        uuid.UUID(collection_id),
        collection_name,
        bucket,
        prefix,
        region,
        endpoint_url,
        access_key,
        secret_key,
        no_sign_request,
        metadata,
        file_types or [],
    )
    _start_job(dict(row))
    return dict(row)


async def resume_incomplete_jobs() -> None:
    """Resume any jobs that were interrupted by a server restart."""
    from bigrag.database import db

    rows = await db.fetch(
        "SELECT * FROM s3_ingest_jobs WHERE status IN ('pending', 'listing', 'ingesting') "
        "ORDER BY created_at"
    )
    if not rows:
        return
    logger.info(f"resuming {len(rows)} incomplete S3 ingest jobs")
    for row in rows:
        _start_job(dict(row))


def _start_job(job: dict) -> None:
    job_id = str(job["id"])
    task = asyncio.create_task(_run_job(job))
    _tasks[job_id] = task
    task.add_done_callback(lambda _: _tasks.pop(job_id, None))


def cancel_job(job_id: str) -> bool:
    """Cancel a running S3 ingest job. Returns True if cancelled."""
    task = _tasks.get(job_id)
    if task and not task.done():
        task.cancel()
        logger.info("s3_job: cancelled", job_id=job_id)
        return True
    return False


async def _run_job(job: dict) -> None:
    """Full lifecycle: list → download → extract → ingest."""
    import aiobotocore.session
    from botocore import UNSIGNED
    from botocore.config import Config
    from botocore.exceptions import NoCredentialsError

    from bigrag.database import db
    from bigrag.services.ingestion_job import create_ingestion_job
    from bigrag.services.queue import ingestion_queue
    from bigrag.services.storage import get_storage

    job_id = str(job["id"])
    collection_name = job["collection_name"]
    collection_id = job["collection_id"]
    bucket = job["bucket"]
    prefix = job["prefix"]
    meta_template = job["metadata"] or {}

    # Build the effective extension filter
    raw_file_types: list[str] = job.get("file_types") or []
    if raw_file_types:
        allowed_extensions = {
            f".{ft.lstrip('.').lower()}" for ft in raw_file_types
        }
        # Only keep extensions that are actually supported
        allowed_extensions &= SUPPORTED_EXTENSIONS
        # Include .tar if any of the allowed types could be inside tars
        ingestable_extensions = allowed_extensions | ({".tar"} if allowed_extensions else set())
    else:
        allowed_extensions = SUPPORTED_EXTENSIONS
        ingestable_extensions = S3_INGESTABLE

    logger.info(
        "s3_job: starting",
        job_id=job_id, bucket=bucket, prefix=prefix,
    )

    # Build S3 client config
    s3_kwargs: dict[str, Any] = {"region_name": job["region"]}
    if job["endpoint_url"]:
        s3_kwargs["endpoint_url"] = job["endpoint_url"]
    if job["no_sign_request"]:
        s3_kwargs["config"] = Config(signature_version=UNSIGNED)
    elif job["access_key"] and job["secret_key"]:
        s3_kwargs["aws_access_key_id"] = job["access_key"]
        s3_kwargs["aws_secret_access_key"] = job["secret_key"]

    session = aiobotocore.session.get_session()

    # --- Update status helper ---
    async def _update(status: str, **fields: Any) -> None:
        parts = ["status = $2", "updated_at = now()"]
        vals: list[Any] = [uuid.UUID(job_id), status]
        idx = 3
        for k, v in fields.items():
            parts.append(f"{k} = ${idx}")
            vals.append(v)
            idx += 1
        await db.execute(
            f"UPDATE s3_ingest_jobs SET {', '.join(parts)} WHERE id = $1", *vals
        )

    # --- List objects ---
    await _update("listing")
    objects: list[dict] = []

    async def _list_objects(kwargs: dict) -> None:
        pages = 0
        async with session.create_client("s3", **kwargs) as s3:
            paginator = s3.get_paginator("list_objects_v2")
            list_kw: dict = {"Bucket": bucket}
            if prefix:
                list_kw["Prefix"] = prefix
            async for page in paginator.paginate(**list_kw):
                pages += 1
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if key.endswith("/"):
                        continue
                    ext = Path(key).suffix.lower()
                    if ext in ingestable_extensions:
                        objects.append(obj)
                if pages % 5 == 0:
                    await _update(
                        "listing", total_found=len(objects),
                    )
                    logger.info(
                        "s3_job: listing",
                        job_id=job_id, found=len(objects), pages=pages,
                    )

    async def _resolve_region() -> str | None:
        # Try GetBucketLocation first
        try:
            kw: dict = {
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

        # Fallback: HEAD request to bucket URL — region is in the response header
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as http:
                r = await http.head(f"https://{bucket}.s3.amazonaws.com")
                region = r.headers.get("x-amz-bucket-region")
                if region:
                    logger.info("s3_job: region from HEAD", region=region)
                    return region
        except Exception:
            pass

        logger.warning("s3_job: could not detect region, using user-supplied")
        return None

    def _is_redirect(exc: Exception) -> bool:
        s = str(exc)
        return "PermanentRedirect" in s or "specified endpoint" in s

    async def _list_with_fallback() -> None:
        """List with automatic credential + region fallback."""
        # 1. Try as-is
        try:
            await _list_objects(s3_kwargs)
            return
        except NoCredentialsError:
            logger.info("s3_job: no credentials, switching to unsigned")
            s3_kwargs["config"] = Config(signature_version=UNSIGNED)
        except Exception as e:
            if not _is_redirect(e):
                raise
            if "config" not in s3_kwargs:
                s3_kwargs["config"] = Config(signature_version=UNSIGNED)

        # 2. Try to detect correct region before listing
        region = await _resolve_region()
        if region and region != s3_kwargs.get("region_name"):
            logger.info("s3_job: detected region", actual=region)
            s3_kwargs["region_name"] = region
            s3_kwargs.pop("endpoint_url", None)

        # 3. List with resolved config
        logger.info(
            "s3_job: listing",
            region=s3_kwargs.get("region_name"),
            unsigned=True,
        )
        await _list_objects(s3_kwargs)

    try:
        await _list_with_fallback()
    except asyncio.CancelledError:
        logger.info("s3_job: cancelled during listing", job_id=job_id)
        return
    except Exception as e:
        logger.error(f"s3_job: listing failed: {e!r}")
        await _update("failed", error_message=str(e))
        return

    if not objects:
        logger.warning("s3_job: no supported files found", bucket=bucket, prefix=prefix)
        await _update("complete", total_found=0)
        return

    await _update("ingesting", total_found=len(objects))
    logger.info("s3_job: found files", count=len(objects), job_id=job_id)

    # --- Get collection for ingestion job creation ---
    from bigrag.config import settings
    from bigrag.routers import get_collection_or_404

    try:
        collection = await get_collection_or_404(collection_name)
    except Exception:
        await _update("failed", error_message="Collection not found")
        return

    # --- Check already-ingested keys (for resume) ---
    existing_rows = await db.fetch(
        "SELECT metadata->>'s3_key' AS s3_key FROM documents WHERE collection_id = $1 "
        "AND metadata->>'source' = 's3' AND metadata->>'s3_bucket' = $2",
        collection_id, bucket,
    )
    existing_keys = {r["s3_key"] for r in existing_rows if r["s3_key"]}

    # --- Download, extract, ingest ---
    storage = get_storage()
    ingested = 0
    skipped = 0

    async def _ingest_file(
        filename: str, file_ext: str, content: bytes, s3_key: str,
    ) -> None:
        nonlocal ingested, skipped
        if s3_key in existing_keys:
            skipped += 1
            return

        doc_id = str(uuid.uuid4())
        storage_key = f"{collection_name}/{doc_id}{file_ext}"
        await storage.put(storage_key, content)

        try:
            await db.fetchrow(
                """
                INSERT INTO documents
                    (id, collection_id, filename, file_type,
                     file_size, file_path, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                uuid.UUID(doc_id),
                collection_id,
                filename,
                file_ext.lstrip("."),
                len(content),
                storage_key,
                {**meta_template, "source": "s3", "s3_bucket": bucket, "s3_key": s3_key},
            )
        except Exception:
            await storage.delete(storage_key)
            skipped += 1
            return

        await ingestion_queue.enqueue(
            create_ingestion_job(
                document_id=doc_id,
                file_path=storage_key,
                collection_name=collection_name,
                collection=collection,
                fallback_api_key=settings.embedding_api_key,
            )
        )
        existing_keys.add(s3_key)
        ingested += 1

        # Update progress in DB
        await _update("ingesting", total_ingested=ingested, total_skipped=skipped)
        if ingested % 10 == 0:
            logger.info(
                "s3_job: ingesting",
                job_id=job_id, ingested=ingested, skipped=skipped,
                total=len(objects),
            )

    max_object_bytes = 2 * 1024 * 1024 * 1024  # 2GB per object
    obj_count = len(objects)
    try:
        async with session.create_client("s3", **s3_kwargs) as s3:
            for idx, obj in enumerate(objects):
                key = obj["Key"]
                file_ext = Path(key).suffix.lower()
                size_bytes = obj.get("Size", 0)
                size_mb = size_bytes / (1024 * 1024)

                if size_bytes > max_object_bytes:
                    logger.warning(
                        "s3_job: skipping oversized object",
                        key=key, size_mb=round(size_mb, 1),
                    )
                    skipped += 1
                    continue

                logger.info(
                    "s3_job: downloading",
                    job_id=job_id,
                    key=key,
                    size_mb=round(size_mb, 1),
                    progress=f"{idx + 1}/{obj_count}",
                )

                try:
                    resp = await s3.get_object(Bucket=bucket, Key=key)
                    content = await resp["Body"].read()
                except Exception as e:
                    logger.warning("s3_job: download failed", key=key, error=str(e))
                    skipped += 1
                    continue

                if len(content) == 0:
                    skipped += 1
                    continue

                if file_ext == ".tar":
                    try:
                        with tarfile.open(fileobj=io.BytesIO(content)) as tar:
                            members = [
                                m for m in tar.getmembers()
                                if m.isfile()
                                and Path(m.name).suffix.lower() in allowed_extensions
                            ]
                            logger.info(
                                "s3_job: extracting tar",
                                key=key,
                                files=len(members),
                            )
                            for member in members:
                                f = tar.extractfile(member)
                                if f is None:
                                    continue
                                data = f.read()
                                if len(data) == 0:
                                    continue
                                await _ingest_file(
                                    Path(member.name).name,
                                    Path(member.name).suffix.lower(),
                                    data,
                                    f"{key}:{member.name}",
                                )
                    except Exception as e:
                        logger.warning("s3_job: tar failed", key=key, error=str(e))
                        skipped += 1
                else:
                    await _ingest_file(Path(key).name, file_ext, content, key)

    except asyncio.CancelledError:
        logger.info("s3_job: cancelled during ingestion", job_id=job_id)
        return
    except Exception as e:
        logger.error(f"s3_job: failed: {e!r}")
        await _update(
            "failed", total_ingested=ingested, total_skipped=skipped,
            error_message=str(e),
        )
        return

    await _update("complete", total_ingested=ingested, total_skipped=skipped)
    logger.info(
        "s3_job: complete",
        job_id=job_id, ingested=ingested, skipped=skipped,
    )
