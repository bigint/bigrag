"""Persistent S3 ingest jobs that survive server restarts."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from bigrag.db.engine import session_factory
from bigrag.db.models import Collection, Document, S3IngestJob
from bigrag.logging import get_logger
from bigrag.services.event_bus import IngestionEvent, event_bus
from bigrag.services.s3_client import (
    SUPPORTED_EXTENSIONS,
    build_s3_kwargs,
    iter_s3_pages,
    resolve_s3_config,
)

logger = get_logger("bigrag.s3_ingest")

_tasks: dict[str, asyncio.Task] = {}  # job_id → task


def _job_to_dict(job: S3IngestJob) -> dict:
    return {
        "id": job.id,
        "collection_id": job.collection_id,
        "collection_name": job.collection_name,
        "bucket": job.bucket,
        "prefix": job.prefix,
        "region": job.region,
        "endpoint_url": job.endpoint_url,
        "access_key": job.access_key,
        "secret_key": job.secret_key,
        "no_sign_request": job.no_sign_request,
        "metadata": job.meta or {},
        "file_types": list(job.file_types or []),
    }


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
    job = S3IngestJob(
        id=uuid.uuid4(),
        collection_id=uuid.UUID(collection_id),
        collection_name=collection_name,
        bucket=bucket,
        prefix=prefix,
        region=region,
        endpoint_url=endpoint_url,
        access_key=access_key,
        secret_key=secret_key,
        no_sign_request=no_sign_request,
        meta=metadata,
        file_types=file_types or [],
    )
    async with session_factory()() as session:
        session.add(job)
        await session.commit()
        await session.refresh(job)
    job_dict = _job_to_dict(job)
    _start_job(job_dict)
    return job_dict


async def resume_incomplete_jobs() -> None:
    """Resume any jobs that were interrupted by a server restart."""
    async with session_factory()() as session:
        jobs = (
            await session.scalars(
                sa.select(S3IngestJob)
                .where(S3IngestJob.status.in_(("pending", "listing", "ingesting")))
                .order_by(S3IngestJob.created_at.asc())
            )
        ).all()
    if not jobs:
        return
    logger.info(f"resuming {len(jobs)} incomplete S3 ingest jobs")
    for job in jobs:
        _start_job(_job_to_dict(job))


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


# Allowlist of columns _update is permitted to touch. Adding a new field?
# Add it here first — otherwise _update raises. Keeps a stray caller from
# smuggling attacker-controlled field names into the SQL even if a future
# refactor makes them user-reachable.
_ALLOWED_UPDATE_FIELDS = frozenset(
    {"error_message", "total_found", "total_ingested", "total_skipped"}
)


async def _run_job(job: dict) -> None:
    """Full lifecycle: list → download → extract → ingest."""
    import aiobotocore.session

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
        unknown = set(fields) - _ALLOWED_UPDATE_FIELDS
        if unknown:
            raise ValueError(f"_update: unknown fields {sorted(unknown)}")
        async with session_factory()() as session:
            await session.execute(
                sa.update(S3IngestJob)
                .where(S3IngestJob.id == uuid.UUID(job_id))
                .values(status=status, **fields)
            )
            await session.commit()

    def _emit(step: str, status: str, msg: str, **detail: Any) -> None:
        event_bus.publish(IngestionEvent(
            document_id=f"s3:{job_id}",
            step=step,
            status=status,
            message=msg,
            detail=detail,
            collection_name=collection_name,
        ))

    _emit("s3_started", "processing", f"S3 import from s3://{bucket}/{prefix}")
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

    async with session_factory()() as session:
        existing_rows = (
            await session.execute(
                sa.select(Document.meta["s3_key"].astext.label("s3_key"))
                .where(Document.collection_id == collection_id)
                .where(Document.meta["source"].astext == "s3")
                .where(Document.meta["s3_bucket"].astext == bucket)
            )
        ).all()
    existing_keys = {r.s3_key for r in existing_rows if r.s3_key}

    storage = get_storage()
    ingested = 0
    skipped = 0
    total_found = 0
    sem = asyncio.Semaphore(10)
    max_object_bytes = 2 * 1024 * 1024 * 1024  # 2GB per object

    await _update("ingesting")

    def _on_listing_progress(count: int) -> None:
        asyncio.ensure_future(_update("ingesting", total_found=count))
        _emit("s3_listing", "processing", f"Found {count} files so far", found=count)
        logger.info("s3_job: listing", job_id=job_id, found=count)

    s3_session = aiobotocore.session.get_session()

    try:
        async with s3_session.create_client("s3", **s3_kwargs) as s3:

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

                        doc_id = uuid.uuid4()
                        storage_key = f"{collection_name}/{doc_id}{file_ext}"
                        await storage.put(storage_key, content)

                    try:
                        async with session_factory()() as session:
                            session.add(
                                Document(
                                    id=doc_id,
                                    collection_id=collection_id,
                                    filename=Path(key).name,
                                    file_type=file_ext.lstrip("."),
                                    file_size=len(content),
                                    file_path=storage_key,
                                    meta={
                                        **meta_template,
                                        "source": "s3",
                                        "s3_bucket": bucket,
                                        "s3_key": key,
                                    },
                                )
                            )
                            await session.commit()
                    except Exception:
                        await storage.delete(storage_key)
                        skipped += 1
                        return

                    try:
                        await ingestion_queue.enqueue(
                            create_ingestion_job(
                                document_id=str(doc_id),
                                file_path=storage_key,
                                collection_name=collection_name,
                                collection=collection,
                                fallback_api_key=settings.embedding_api_key,
                            )
                        )
                    except Exception:
                        async with session_factory()() as session:
                            await session.execute(
                                sa.delete(Document).where(Document.id == doc_id)
                            )
                            await session.commit()
                        await storage.delete(storage_key)
                        skipped += 1
                        return

                    ingested += 1
                    _emit(
                        "s3_ingested", "processing",
                        f"Ingested {Path(key).name}",
                        ingested=ingested, skipped=skipped, found=total_found,
                    )
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
                page_skipped = 0
                for obj in page:
                    key = obj["Key"]
                    total_found += 1
                    if key in existing_keys:
                        skipped += 1
                        page_skipped += 1
                    else:
                        existing_keys.add(key)
                        new_objects.append(obj)

                if page_skipped:
                    _emit(
                        "s3_skipped", "processing",
                        f"Skipped {page_skipped} already-ingested files",
                        skipped=skipped, found=total_found,
                    )

                if new_objects:
                    await asyncio.gather(
                        *(_download_and_ingest(o) for o in new_objects)
                    )

    except asyncio.CancelledError:
        _emit("s3_cancelled", "failed", "S3 import cancelled")
        logger.info("s3_job: cancelled during ingestion", job_id=job_id)
        return
    except Exception as e:
        _emit("s3_failed", "failed", f"S3 import failed: {e}")
        logger.error(f"s3_job: failed: {e!r}")
        await _update(
            "failed", total_ingested=ingested, total_skipped=skipped,
            error_message=str(e),
        )
        return

    if total_found == 0:
        logger.warning("s3_job: no supported files found", bucket=bucket, prefix=prefix)

    _emit(
        "s3_complete", "complete",
        f"S3 import done — {ingested} ingested, {skipped} skipped",
        ingested=ingested, skipped=skipped, found=total_found,
    )
    await _update(
        "complete", total_found=total_found,
        total_ingested=ingested, total_skipped=skipped,
    )
    logger.info(
        "s3_job: complete",
        job_id=job_id, ingested=ingested, skipped=skipped, found=total_found,
    )


# keep module imports referenced — alembic/migrations hook introspection
_ = Collection
