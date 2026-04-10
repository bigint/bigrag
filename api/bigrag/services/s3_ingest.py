"""Persistent S3 ingest jobs that survive server restarts."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from bigrag.logging import get_logger
from bigrag.services.s3_client import (
    SUPPORTED_EXTENSIONS,
    build_s3_kwargs,
    iter_s3_pages,
    resolve_s3_config,
)

logger = get_logger("bigrag.s3_ingest")

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


async def cancel_job(job_id: str) -> bool:
    """Cancel a running S3 ingest job and wait for it to stop."""
    task = _tasks.get(job_id)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        logger.info("s3_job: cancelled", job_id=job_id)
        return True
    return False


async def _run_job(job: dict) -> None:
    """Full lifecycle: list → download → extract → ingest."""
    import aiobotocore.session

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

    raw_file_types: list[str] = job.get("file_types") or []
    if raw_file_types:
        extensions = {f".{ft.lstrip('.').lower()}" for ft in raw_file_types}
        extensions &= SUPPORTED_EXTENSIONS
    else:
        extensions = SUPPORTED_EXTENSIONS

    logger.info(
        "s3_job: starting",
        job_id=job_id, bucket=bucket, prefix=prefix,
    )

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

    await _update("listing")
    s3_kwargs = build_s3_kwargs(job)

    try:
        s3_kwargs = await resolve_s3_config(bucket, prefix, s3_kwargs)
    except asyncio.CancelledError:
        logger.info("s3_job: cancelled during config resolve", job_id=job_id)
        return
    except Exception as e:
        logger.error(f"s3_job: s3 access failed: {e!r}")
        await _update("failed", error_message=str(e))
        return

    from bigrag.config import settings
    from bigrag.routers import get_collection_or_404

    try:
        collection = await get_collection_or_404(collection_name)
    except Exception:
        await _update("failed", error_message="Collection not found")
        return

    existing_rows = await db.fetch(
        "SELECT metadata->>'s3_key' AS s3_key FROM documents WHERE collection_id = $1 "
        "AND metadata->>'source' = 's3' AND metadata->>'s3_bucket' = $2",
        collection_id, bucket,
    )
    existing_keys = {r["s3_key"] for r in existing_rows if r["s3_key"]}

    storage = get_storage()
    ingested = 0
    skipped = 0
    total_found = 0
    sem = asyncio.Semaphore(10)
    max_object_bytes = 2 * 1024 * 1024 * 1024  # 2GB per object

    await _update("ingesting")

    def _on_listing_progress(count: int) -> None:
        asyncio.ensure_future(_update("ingesting", total_found=count))
        logger.info("s3_job: listing", job_id=job_id, found=count)

    session = aiobotocore.session.get_session()

    try:
        async with session.create_client("s3", **s3_kwargs) as s3:

            async def _download_and_ingest(obj: dict) -> None:
                nonlocal ingested, skipped
                key = obj["Key"]
                try:
                    file_ext = Path(key).suffix.lower()
                    size_bytes = obj.get("Size", 0)
                    size_mb = size_bytes / (1024 * 1024)

                    if size_bytes > max_object_bytes:
                        logger.warning(
                            "s3_job: skipping oversized object",
                            key=key, size_mb=round(size_mb, 1),
                        )
                        skipped += 1
                        return

                    async with sem:
                        logger.info(
                            "s3_job: downloading",
                            job_id=job_id, key=key,
                            size_mb=round(size_mb, 1),
                        )

                        try:
                            resp = await s3.get_object(Bucket=bucket, Key=key)
                            content = await resp["Body"].read()
                        except Exception as e:
                            logger.warning("s3_job: download failed", key=key, error=str(e))
                            skipped += 1
                            return

                        if len(content) == 0:
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
                            Path(key).name,
                            file_ext.lstrip("."),
                            len(content),
                            storage_key,
                            {**meta_template, "source": "s3", "s3_bucket": bucket, "s3_key": key},
                        )
                    except Exception:
                        await storage.delete(storage_key)
                        skipped += 1
                        return

                    try:
                        await ingestion_queue.enqueue(
                            create_ingestion_job(
                                document_id=doc_id,
                                file_path=storage_key,
                                collection_name=collection_name,
                                collection=collection,
                                fallback_api_key=settings.embedding_api_key,
                            )
                        )
                    except Exception:
                        await db.execute("DELETE FROM documents WHERE id = $1", uuid.UUID(doc_id))
                        await storage.delete(storage_key)
                        skipped += 1
                        return

                    ingested += 1
                    if ingested % 10 == 0:
                        await _update(
                            "ingesting", total_found=total_found,
                            total_ingested=ingested, total_skipped=skipped,
                        )
                        logger.info(
                            "s3_job: ingesting",
                            job_id=job_id, ingested=ingested,
                            skipped=skipped, found=total_found,
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning("s3_job: failed to process", key=key, error=str(e))
                    skipped += 1

            async for page in iter_s3_pages(
                bucket=bucket,
                prefix=prefix,
                s3_kwargs=s3_kwargs,
                extensions=extensions,
                on_progress=_on_listing_progress,
            ):
                new_objects: list[dict] = []
                for obj in page:
                    key = obj["Key"]
                    total_found += 1
                    if key in existing_keys:
                        skipped += 1
                    else:
                        existing_keys.add(key)
                        new_objects.append(obj)

                if new_objects:
                    await asyncio.gather(
                        *(_download_and_ingest(o) for o in new_objects)
                    )

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

    if total_found == 0:
        logger.warning("s3_job: no supported files found", bucket=bucket, prefix=prefix)

    await _update(
        "complete", total_found=total_found,
        total_ingested=ingested, total_skipped=skipped,
    )
    logger.info(
        "s3_job: complete",
        job_id=job_id, ingested=ingested, skipped=skipped, found=total_found,
    )
