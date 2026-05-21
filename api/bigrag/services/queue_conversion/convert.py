from __future__ import annotations

import asyncio
import time
from pathlib import Path

from bigrag.logging import get_logger
from bigrag.services.conversion import convert_document_path_isolated
from bigrag.services.document_elements import ParsedDocument, parsed_document_from_text
from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.queue_conversion.pdf_ocr import ocr_scanned_pdf

logger = get_logger("bigrag.queue")

PLAIN_TEXT_EXTS = {".txt", ".csv", ".tsv", ".md", ".json", ".xml"}


async def convert_document(
    job: IngestionJob,
    prefix: str,
    *,
    emit,
    ensure_job_current,
) -> ParsedDocument:
    import tempfile

    from bigrag.services.runtime_settings import get_values
    from bigrag.services.storage import get_storage

    emit(
        job.document_id,
        "converting",
        "processing",
        "Parsing document",
        0.15,
        collection_name=job.collection_name,
    )
    t0 = time.monotonic()

    runtime = await get_values(["conversion_timeout", "conversion_pdf_ocr_enabled"])
    conversion_timeout = runtime["conversion_timeout"]
    pdf_ocr_enabled = runtime["conversion_pdf_ocr_enabled"]
    suffix = Path(job.file_path).suffix.lower()
    storage = get_storage()
    include_elements = job.multimodal_enabled or job.multimodal_enrichment_enabled

    def _make_tmp() -> str:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.close()
        return tmp.name

    tmp_path = await asyncio.to_thread(_make_tmp)
    bytes_written = 0
    try:

        def _open_write():
            return open(tmp_path, "wb")

        fh = await asyncio.to_thread(_open_write)
        try:
            async for chunk in storage.get_stream(job.file_path):
                await asyncio.to_thread(fh.write, chunk)
                bytes_written += len(chunk)
        finally:
            await asyncio.to_thread(fh.close)

        logger.info(
            "conversion start",
            prefix=prefix,
            collection=job.collection_name,
            file_path=job.file_path,
            suffix=suffix,
            bytes=bytes_written,
        )

        if suffix in PLAIN_TEXT_EXTS:

            def _read_text() -> str:
                with open(tmp_path, "rb") as rfh:
                    return rfh.read().decode("utf-8", errors="replace")

            text = await asyncio.to_thread(_read_text)
            if not text.strip():
                raise ValueError("Document produced no extractable text")
            parsed = parsed_document_from_text(
                text,
                suffix=suffix,
                source_asset_path=job.file_path,
                include_elements=include_elements,
            )
            elapsed = time.monotonic() - t0
            logger.info("plain text read", prefix=prefix, elapsed=round(elapsed, 2))
            emit(
                job.document_id,
                "text_extracted",
                "processing",
                f"Extracted {len(text):,} characters",
                0.40,
                collection_name=job.collection_name,
                chars=len(text),
            )
            return parsed

        logger.info(
            "isolated converter start",
            prefix=prefix,
            suffix=suffix,
            timeout=conversion_timeout,
            pdf_ocr_enabled=pdf_ocr_enabled,
        )
        if suffix == ".pdf":
            try:
                parsed = await convert_document_path_isolated(
                    tmp_path,
                    suffix,
                    pdf_ocr_enabled=False,
                    timeout=conversion_timeout,
                    include_elements=include_elements,
                    source_asset_path=job.file_path,
                )
            except TimeoutError as e:
                raise ValueError(str(e)) from e
            if parsed.text.strip() or not pdf_ocr_enabled:
                elapsed = time.monotonic() - t0
                logger.info(
                    "pdf text conversion complete", prefix=prefix, elapsed=round(elapsed, 2)
                )
                emit(
                    job.document_id,
                    "converted",
                    "processing",
                    f"Parsed in {elapsed:.1f}s",
                    0.35,
                    collection_name=job.collection_name,
                    elapsed=round(elapsed, 2),
                )
                if not parsed.text.strip():
                    raise ValueError("Document produced no extractable text")
                logger.info("text extracted", prefix=prefix, chars=len(parsed.text))
                emit(
                    job.document_id,
                    "text_extracted",
                    "processing",
                    f"Extracted {len(parsed.text):,} characters",
                    0.40,
                    collection_name=job.collection_name,
                    chars=len(parsed.text),
                )
                return parsed
            text = await ocr_scanned_pdf(
                tmp_path=tmp_path,
                suffix=suffix,
                job=job,
                prefix=prefix,
                start_time=t0,
                emit=emit,
                ensure_job_current=ensure_job_current,
            )
            return parsed_document_from_text(
                text,
                suffix=suffix,
                source_asset_path=job.file_path,
                include_elements=include_elements,
            )

        try:
            parsed = await convert_document_path_isolated(
                tmp_path,
                suffix,
                pdf_ocr_enabled=pdf_ocr_enabled,
                timeout=conversion_timeout,
                include_elements=include_elements,
                source_asset_path=job.file_path,
            )
        except TimeoutError as e:
            raise ValueError(str(e)) from e

        elapsed = time.monotonic() - t0
        logger.info("isolated conversion complete", prefix=prefix, elapsed=round(elapsed, 2))
        emit(
            job.document_id,
            "converted",
            "processing",
            f"Parsed in {elapsed:.1f}s",
            0.35,
            collection_name=job.collection_name,
            elapsed=round(elapsed, 2),
        )

        if not parsed.text.strip():
            raise ValueError("Document produced no extractable text")

        logger.info("text extracted", prefix=prefix, chars=len(parsed.text))
        emit(
            job.document_id,
            "text_extracted",
            "processing",
            f"Extracted {len(parsed.text):,} characters",
            0.40,
            collection_name=job.collection_name,
            chars=len(parsed.text),
        )
        return parsed
    finally:
        await asyncio.to_thread(Path(tmp_path).unlink, True)
