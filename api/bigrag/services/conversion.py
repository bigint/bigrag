from __future__ import annotations

import threading
import time
from pathlib import Path

from bigrag.logging import get_logger

logger = get_logger("bigrag.conversion")

_docling_converters = {}
_docling_lock = threading.Lock()


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

        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, InputFormat, PdfFormatOption
        from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

        pdf_opts = PdfPipelineOptions()
        pdf_opts.do_ocr = pdf_ocr_enabled

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    pipeline_options=pdf_opts,
                )
            }
        )
        _docling_converters[pdf_ocr_enabled] = converter
        logger.info("docling converter load complete", pdf_ocr_enabled=pdf_ocr_enabled)

    return converter
