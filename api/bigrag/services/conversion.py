from __future__ import annotations

import logging

logger = logging.getLogger("bigrag.conversion")

_docling_converter = None


def _get_docling_converter():
    global _docling_converter
    if _docling_converter is None:
        import os

        # Use HF cache if models are already downloaded, otherwise allow download
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
            except Exception:
                pass  # scan_cache_dir failed, let HF decide

        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, InputFormat, PdfFormatOption
        from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

        pdf_opts = PdfPipelineOptions()
        pdf_opts.do_ocr = True

        _docling_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    pipeline_options=pdf_opts,
                )
            }
        )
    return _docling_converter
