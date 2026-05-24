from __future__ import annotations

import asyncio
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

from bigrag.config import settings
from bigrag.logging import get_logger
from bigrag.services.document_elements import (
    ParsedDocument,
    parsed_document_from_docling_result,
    parsed_document_from_text,
)

logger = get_logger("bigrag.conversion")

MAX_EXTRACTED_TEXT_CHARS = 50_000_000

_docling_converters = {}
_docling_lock = threading.Lock()

_executor: ProcessPoolExecutor | None = None
_executor_lock: asyncio.Lock | None = None
_conversion_semaphore: asyncio.Semaphore | None = None
_semaphore_lock: asyncio.Lock | None = None


def extract_pdf_text(path: str | Path) -> str:
    from pypdfium2 import PdfDocument

    t0 = time.monotonic()
    pdf = PdfDocument(str(path))
    pages: list[str] = []
    total_pages = 0
    try:
        total_pages = len(pdf)
        logger.info("pdf text extraction opened", pages=total_pages)
        for page_index in range(total_pages):
            page = pdf[page_index]
            try:
                text_page = page.get_textpage()
                try:
                    text = text_page.get_text_range().strip()
                finally:
                    text_page.close()
            finally:
                page.close()

            if text:
                pages.append(text)
            if (page_index + 1) % 100 == 0 or page_index + 1 == total_pages:
                logger.info(
                    "pdf text extraction progress",
                    pages_done=page_index + 1,
                    pages_total=total_pages,
                    text_pages=len(pages),
                )
    finally:
        pdf.close()

    text = "\n\n".join(pages)
    logger.info(
        "pdf text extraction complete",
        pages_total=total_pages,
        text_pages=len(pages),
        chars=len(text),
        elapsed=round(time.monotonic() - t0, 2),
    )
    return text


def get_pdf_page_count(path: str | Path) -> int:
    from pypdfium2 import PdfDocument

    pdf = PdfDocument(str(path))
    try:
        return len(pdf)
    finally:
        pdf.close()


def _get_docling_converter(*, pdf_ocr_enabled: bool = True):
    cached = _docling_converters.get(pdf_ocr_enabled)
    if cached is not None:
        return cached

    with _docling_lock:
        cached = _docling_converters.get(pdf_ocr_enabled)
        if cached is not None:
            return cached
        import os

        logger.info("docling converter load start", pdf_ocr_enabled=pdf_ocr_enabled)

        if os.environ.get("HF_HUB_OFFLINE") is None:
            from huggingface_hub import scan_cache_dir

            try:
                cache = scan_cache_dir()
                cached_repos = {r.repo_id for r in cache.repos}
                if "docling-project/docling-layout-heron" in cached_repos:
                    os.environ["HF_HUB_OFFLINE"] = "1"
                    logger.info("Docling models cached — using HF offline mode")
                else:
                    logger.info("Docling models not cached — will download from HF")
            except (OSError, PermissionError) as exc:
                logger.debug("hf cache scan failed, deferring to HF", error=str(exc))

        from docling.datamodel.accelerator_options import AcceleratorOptions
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import (
            DocumentConverter,
            ImageFormatOption,
            InputFormat,
            PdfFormatOption,
        )
        from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

        pdf_opts = PdfPipelineOptions()
        pdf_opts.accelerator_options = AcceleratorOptions(device=settings.conversion_device)
        pdf_opts.do_ocr = pdf_ocr_enabled
        if hasattr(pdf_opts, "generate_picture_images"):
            pdf_opts.generate_picture_images = True
        image_opts = pdf_opts.model_copy(deep=True)
        image_opts.do_ocr = True

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    pipeline_options=pdf_opts,
                ),
                InputFormat.IMAGE: ImageFormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    pipeline_options=image_opts,
                ),
            }
        )
        _docling_converters[pdf_ocr_enabled] = converter
        logger.info("docling converter load complete", pdf_ocr_enabled=pdf_ocr_enabled)

    return converter


def _guard_extracted_length(text: str) -> None:
    if len(text) > MAX_EXTRACTED_TEXT_CHARS:
        raise ValueError(
            f"Extracted text length {len(text)} exceeds the maximum of "
            f"{MAX_EXTRACTED_TEXT_CHARS} characters"
        )


def _convert_file_path(
    path: str,
    suffix: str,
    pdf_ocr_enabled: bool,
    include_elements: bool,
) -> ParsedDocument:
    if suffix == ".pdf" and not include_elements:
        text = extract_pdf_text(path)
        if text.strip() or not pdf_ocr_enabled:
            _guard_extracted_length(text)
            return parsed_document_from_text(
                text,
                suffix=suffix,
                include_elements=False,
            )
    converter = _get_docling_converter(pdf_ocr_enabled=pdf_ocr_enabled)
    parsed = parsed_document_from_docling_result(
        converter.convert(path),
        suffix=suffix,
        include_elements=include_elements,
    )
    _guard_extracted_length(parsed.text)
    return parsed


def _pool_convert(
    path: str,
    suffix: str,
    pdf_ocr_enabled: bool,
    include_elements: bool,
) -> ParsedDocument:
    return _convert_file_path(
        path,
        suffix,
        pdf_ocr_enabled,
        include_elements,
    )


def _pool_ocr_chunk(path: str, page_start: int, page_end: int) -> str:
    converter = _get_docling_converter(pdf_ocr_enabled=True)
    result = converter.convert(path, page_range=(page_start, page_end))
    doc = getattr(result, "document", None)
    if doc is not None:
        md = getattr(doc, "export_to_markdown", None)
        text = md() if callable(md) else ""
        if not text or not text.strip():
            txt = getattr(doc, "export_to_text", None)
            if callable(txt):
                text = txt()
        return text or ""
    return str(result)


async def get_conversion_executor() -> ProcessPoolExecutor:
    global _executor, _executor_lock
    if _executor is not None:
        return _executor
    if _executor_lock is None:
        _executor_lock = asyncio.Lock()
    async with _executor_lock:
        if _executor is not None:
            return _executor
        max_workers = settings.conversion_pool_workers
        logger.info("conversion pool starting", max_workers=max_workers)
        _executor = ProcessPoolExecutor(
            max_workers=max_workers,
            mp_context=get_context("spawn"),
        )
        return _executor


async def shutdown_conversion_executor() -> None:
    global _executor
    executor = _executor
    if executor is None:
        return
    _executor = None
    logger.info("conversion pool shutting down")
    await asyncio.to_thread(executor.shutdown, True, cancel_futures=True)


async def _get_conversion_semaphore() -> asyncio.Semaphore:
    global _conversion_semaphore, _semaphore_lock
    if _conversion_semaphore is not None:
        return _conversion_semaphore
    if _semaphore_lock is None:
        _semaphore_lock = asyncio.Lock()
    async with _semaphore_lock:
        if _conversion_semaphore is not None:
            return _conversion_semaphore
        _conversion_semaphore = asyncio.Semaphore(settings.conversion_pool_workers)
        return _conversion_semaphore


async def convert_document_path_isolated(
    path: str,
    suffix: str,
    *,
    pdf_ocr_enabled: bool,
    timeout: int,
    include_elements: bool = False,
) -> ParsedDocument:
    executor = await get_conversion_executor()
    semaphore = await _get_conversion_semaphore()
    loop = asyncio.get_running_loop()
    async with semaphore:
        future = loop.run_in_executor(
            executor,
            _pool_convert,
            path,
            suffix,
            pdf_ocr_enabled,
            include_elements,
        )
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except TimeoutError as exc:
            future.cancel()
            raise TimeoutError(f"Document conversion timed out after {timeout}s") from exc


async def ocr_chunk_in_executor(
    path: str,
    page_start: int,
    page_end: int,
    *,
    timeout: int,
) -> str:
    executor = await get_conversion_executor()
    semaphore = await _get_conversion_semaphore()
    loop = asyncio.get_running_loop()
    async with semaphore:
        future = loop.run_in_executor(
            executor,
            _pool_ocr_chunk,
            path,
            page_start,
            page_end,
        )
        return await asyncio.wait_for(future, timeout=timeout)
