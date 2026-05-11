from __future__ import annotations

import threading
import time
from multiprocessing import Pipe, get_context
from multiprocessing.connection import Connection
from pathlib import Path

from rag_computer.logging import get_logger

logger = get_logger("rag_computer.conversion")

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


def _docling_result_text(result) -> str:
    doc = getattr(result, "document", None)
    if doc is not None:
        for method in ("export_to_markdown", "export_to_text"):
            fn = getattr(doc, method, None)
            if callable(fn):
                try:
                    text = fn()
                    if text:
                        return str(text)
                except Exception:
                    continue
    return str(result)


def _convert_file_path(path: str, suffix: str, pdf_ocr_enabled: bool) -> str:
    if suffix == ".pdf":
        text = extract_pdf_text(path)
        if text.strip() or not pdf_ocr_enabled:
            return text
    converter = _get_docling_converter(pdf_ocr_enabled=pdf_ocr_enabled)
    return _docling_result_text(converter.convert(path))


def _conversion_worker(
    conn: Connection,
    path: str,
    suffix: str,
    pdf_ocr_enabled: bool,
) -> None:
    try:
        conn.send(("ok", _convert_file_path(path, suffix, pdf_ocr_enabled)))
    except Exception as exc:
        conn.send(("error", f"{exc.__class__.__name__}: {exc}"))
    finally:
        conn.close()


def convert_document_isolated(
    file_data: bytes,
    suffix: str,
    *,
    pdf_ocr_enabled: bool,
    timeout: int,
) -> str:
    import tempfile

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = tmp.name
    try:
        tmp.write(file_data)
        tmp.close()
        return _convert_document_path_isolated(
            tmp_path,
            suffix,
            pdf_ocr_enabled=pdf_ocr_enabled,
            timeout=timeout,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _convert_document_path_isolated(
    path: str,
    suffix: str,
    *,
    pdf_ocr_enabled: bool,
    timeout: int,
) -> str:
    ctx = get_context("spawn")
    parent_conn, child_conn = Pipe(duplex=False)
    process = ctx.Process(
        target=_conversion_worker,
        args=(child_conn, path, suffix, pdf_ocr_enabled),
    )
    process.start()
    child_conn.close()
    try:
        if not parent_conn.poll(timeout):
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join(5)
            raise TimeoutError(f"Document conversion timed out after {timeout}s")
        status, payload = parent_conn.recv()
        process.join(5)
        if status == "ok":
            return payload
        raise ValueError(payload)
    finally:
        parent_conn.close()
        if process.is_alive():
            process.terminate()
            process.join(5)
