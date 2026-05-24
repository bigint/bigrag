from __future__ import annotations

import time

from bigrag.logging import get_logger
from bigrag.services.document_elements import ParsedDocument, parsed_document_from_text
from bigrag.services.ingestion_job import IngestionJob
from bigrag.services.queue_conversion.events import (
    emit_conversion_started,
    emit_converted,
    emit_text_extracted,
)
from bigrag.services.queue_conversion.pdf_ocr import ocr_scanned_pdf
from bigrag.services.queue_conversion.plain_text import PLAIN_TEXT_EXTS, parse_plain_text
from bigrag.services.queue_conversion.settings import load_conversion_settings
from bigrag.services.queue_conversion.staging import remove_staged_document, stage_document
from bigrag.services.queue_conversion.structured import (
    convert_pdf_without_ocr,
    convert_staged_document,
)

logger = get_logger("bigrag.queue")


async def convert_document(
    job: IngestionJob,
    prefix: str,
    *,
    emit,
    ensure_job_current,
) -> ParsedDocument:
    emit_conversion_started(job, emit)
    started_at = time.monotonic()
    settings = await load_conversion_settings()
    staged = await stage_document(job)
    include_elements = job.multimodal_enabled or job.multimodal_enrichment_enabled

    try:
        logger.debug(
            "conversion start",
            prefix=prefix,
            collection=job.collection_name,
            file_path=job.file_path,
            suffix=staged.suffix,
            bytes=staged.bytes_written,
        )

        if staged.suffix in PLAIN_TEXT_EXTS:
            parsed = await parse_plain_text(staged, include_elements=include_elements)
            elapsed = time.monotonic() - started_at
            logger.debug("plain text read", prefix=prefix, elapsed=round(elapsed, 2))
            emit_text_extracted(job, emit, parsed.text)
            return parsed

        logger.debug(
            "isolated converter start",
            prefix=prefix,
            suffix=staged.suffix,
            timeout=settings.timeout,
            pdf_ocr_enabled=settings.pdf_ocr_enabled,
        )
        if staged.suffix == ".pdf":
            parsed = await convert_pdf_without_ocr(
                staged,
                settings=settings,
                include_elements=include_elements,
            )
            if parsed.text.strip() or not settings.pdf_ocr_enabled:
                elapsed = emit_converted(job, emit, started_at)
                logger.debug(
                    "pdf text conversion complete", prefix=prefix, elapsed=round(elapsed, 2)
                )
                if not parsed.text.strip():
                    raise ValueError("Document produced no extractable text")
                logger.debug("text extracted", prefix=prefix, chars=len(parsed.text))
                emit_text_extracted(job, emit, parsed.text)
                return parsed
            text = await ocr_scanned_pdf(
                tmp_path=staged.path,
                job=job,
                prefix=prefix,
                start_time=started_at,
                emit=emit,
                ensure_job_current=ensure_job_current,
            )
            return parsed_document_from_text(
                text,
                suffix=staged.suffix,
                include_elements=include_elements,
            )

        parsed = await convert_staged_document(
            staged,
            settings=settings,
            include_elements=include_elements,
        )

        elapsed = emit_converted(job, emit, started_at)
        logger.debug("isolated conversion complete", prefix=prefix, elapsed=round(elapsed, 2))

        if not parsed.text.strip():
            raise ValueError("Document produced no extractable text")

        logger.debug("text extracted", prefix=prefix, chars=len(parsed.text))
        emit_text_extracted(job, emit, parsed.text)
        return parsed
    finally:
        await remove_staged_document(staged.path)
