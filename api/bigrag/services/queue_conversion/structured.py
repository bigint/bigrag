from __future__ import annotations

from bigrag.services.conversion import convert_document_path_isolated
from bigrag.services.document_elements import ParsedDocument
from bigrag.services.queue_conversion.settings import ConversionSettings
from bigrag.services.queue_conversion.staging import StagedDocument


async def convert_staged_document(
    staged: StagedDocument,
    *,
    settings: ConversionSettings,
    include_elements: bool,
) -> ParsedDocument:
    try:
        return await convert_document_path_isolated(
            staged.path,
            staged.suffix,
            pdf_ocr_enabled=settings.pdf_ocr_enabled,
            timeout=settings.timeout,
            include_elements=include_elements,
        )
    except TimeoutError as e:
        raise ValueError(str(e)) from e


async def convert_pdf_without_ocr(
    staged: StagedDocument,
    *,
    settings: ConversionSettings,
    include_elements: bool,
) -> ParsedDocument:
    try:
        return await convert_document_path_isolated(
            staged.path,
            staged.suffix,
            pdf_ocr_enabled=False,
            timeout=settings.timeout,
            include_elements=include_elements,
        )
    except TimeoutError as e:
        raise ValueError(str(e)) from e
