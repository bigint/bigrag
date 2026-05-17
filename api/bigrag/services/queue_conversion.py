from __future__ import annotations

import asyncio
import time
from pathlib import Path

from bigrag.logging import get_logger
from bigrag.services.conversion import (
    convert_document_path_isolated,
    get_pdf_page_count,
    ocr_chunk_in_executor,
)
from bigrag.services.ingestion_job import IngestionJob

logger = get_logger("bigrag.queue")

PLAIN_TEXT_EXTS = {".txt", ".csv", ".tsv", ".md", ".json", ".xml"}
PDF_OCR_CHUNK_PAGES = 10
PDF_OCR_PROGRESS_START = 0.16
PDF_OCR_PROGRESS_END = 0.35


def docling_result_text(result) -> str:
    text = result.document.export_to_markdown()
    if not text.strip():
        text = result.document.export_to_text()
    return text


async def ocr_scanned_pdf(
    *,
    tmp_path: str,
    suffix: str,
    job: IngestionJob,
    prefix: str,
    start_time: float,
    emit,
    ensure_job_current,
) -> str:
    from bigrag.services.runtime_settings import get_values

    runtime = await get_values(["conversion_timeout"])
    conversion_timeout = runtime["conversion_timeout"]
    current_start = 0
    current_end = 0
    total_pages = await asyncio.to_thread(get_pdf_page_count, tmp_path)
    if total_pages <= 0:
        raise ValueError("PDF contains no pages")

    chunk_pages = PDF_OCR_CHUNK_PAGES
    total_chunks = (total_pages + chunk_pages - 1) // chunk_pages
    logger.info(
        "scanned pdf OCR start",
        prefix=prefix,
        pages=total_pages,
        chunk_pages=chunk_pages,
        timeout_per_chunk=conversion_timeout,
    )
    emit(
        job.document_id,
        "ocr",
        "processing",
        f"OCRing scanned PDF ({total_pages:,} pages)",
        PDF_OCR_PROGRESS_START,
        collection_name=job.collection_name,
        pages_total=total_pages,
        chunk_pages=chunk_pages,
    )

    texts: list[str] = []

    for chunk_index, current_start in enumerate(
        range(1, total_pages + 1, chunk_pages),
        start=1,
    ):
        current_end = min(current_start + chunk_pages - 1, total_pages)
        await ensure_job_current(job)
        chunk_progress = PDF_OCR_PROGRESS_START + (
            (PDF_OCR_PROGRESS_END - PDF_OCR_PROGRESS_START) * ((current_start - 1) / total_pages)
        )
        emit(
            job.document_id,
            "ocr",
            "processing",
            f"OCR pages {current_start:,}-{current_end:,} of {total_pages:,}",
            chunk_progress,
            collection_name=job.collection_name,
            page_start=current_start,
            page_end=current_end,
            pages_total=total_pages,
            chunk=chunk_index,
            total_chunks=total_chunks,
        )

        chunk_start_time = time.monotonic()
        try:
            chunk_text_raw = await ocr_chunk_in_executor(
                tmp_path,
                current_start,
                current_end,
                timeout=conversion_timeout,
            )
        except TimeoutError as e:
            raise ValueError(
                "Scanned PDF OCR timed out while processing "
                f"pages {current_start}-{current_end} after "
                f"{conversion_timeout}s"
            ) from e

        chunk_text = chunk_text_raw.strip()
        if chunk_text:
            texts.append(chunk_text)

        elapsed = time.monotonic() - chunk_start_time
        pages_done = current_end
        progress = PDF_OCR_PROGRESS_START + (
            (PDF_OCR_PROGRESS_END - PDF_OCR_PROGRESS_START) * (pages_done / total_pages)
        )
        logger.info(
            "scanned pdf OCR chunk complete",
            prefix=prefix,
            page_start=current_start,
            page_end=current_end,
            pages_total=total_pages,
            chunk=chunk_index,
            total_chunks=total_chunks,
            chars=len(chunk_text),
            elapsed=round(elapsed, 2),
        )
        emit(
            job.document_id,
            "ocr",
            "processing",
            f"OCRed pages {current_start:,}-{current_end:,} of {total_pages:,}",
            progress,
            collection_name=job.collection_name,
            page_start=current_start,
            page_end=current_end,
            pages_done=pages_done,
            pages_total=total_pages,
            chunk=chunk_index,
            total_chunks=total_chunks,
            chars=len(chunk_text),
            elapsed=round(elapsed, 2),
        )

    text = "\n\n".join(texts)
    if not text.strip():
        raise ValueError("Document produced no extractable text")

    elapsed = time.monotonic() - start_time
    logger.info(
        "scanned pdf OCR complete",
        prefix=prefix,
        pages_total=total_pages,
        chunks=total_chunks,
        chars=len(text),
        elapsed=round(elapsed, 2),
    )
    emit(
        job.document_id,
        "converted",
        "processing",
        f"OCR parsed {total_pages:,} pages in {elapsed:.1f}s",
        PDF_OCR_PROGRESS_END,
        collection_name=job.collection_name,
        pages_total=total_pages,
        chunks=total_chunks,
        elapsed=round(elapsed, 2),
    )
    emit(
        job.document_id,
        "text_extracted",
        "processing",
        f"Extracted {len(text):,} characters",
        0.40,
        collection_name=job.collection_name,
        chars=len(text),
    )
    return text


async def convert_document(
    job: IngestionJob,
    prefix: str,
    *,
    emit,
    ensure_job_current,
) -> str:
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
            return text

        logger.info(
            "isolated converter start",
            prefix=prefix,
            suffix=suffix,
            timeout=conversion_timeout,
            pdf_ocr_enabled=pdf_ocr_enabled,
        )
        if suffix == ".pdf":
            try:
                text = await convert_document_path_isolated(
                    tmp_path,
                    suffix,
                    pdf_ocr_enabled=False,
                    timeout=conversion_timeout,
                )
            except TimeoutError as e:
                raise ValueError(str(e)) from e
            if text.strip() or not pdf_ocr_enabled:
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
                if not text.strip():
                    raise ValueError("Document produced no extractable text")
                logger.info("text extracted", prefix=prefix, chars=len(text))
                emit(
                    job.document_id,
                    "text_extracted",
                    "processing",
                    f"Extracted {len(text):,} characters",
                    0.40,
                    collection_name=job.collection_name,
                    chars=len(text),
                )
                return text
            return await ocr_scanned_pdf(
                tmp_path=tmp_path,
                suffix=suffix,
                job=job,
                prefix=prefix,
                start_time=t0,
                emit=emit,
                ensure_job_current=ensure_job_current,
            )

        try:
            text = await convert_document_path_isolated(
                tmp_path,
                suffix,
                pdf_ocr_enabled=pdf_ocr_enabled,
                timeout=conversion_timeout,
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

        if not text.strip():
            raise ValueError("Document produced no extractable text")

        logger.info("text extracted", prefix=prefix, chars=len(text))
        emit(
            job.document_id,
            "text_extracted",
            "processing",
            f"Extracted {len(text):,} characters",
            0.40,
            collection_name=job.collection_name,
            chars=len(text),
        )
        return text
    finally:
        await asyncio.to_thread(Path(tmp_path).unlink, True)
