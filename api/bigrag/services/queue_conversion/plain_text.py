from __future__ import annotations

import asyncio

from bigrag.services.document_elements import ParsedDocument, parsed_document_from_text
from bigrag.services.queue_conversion.staging import StagedDocument

PLAIN_TEXT_EXTS = {".txt", ".csv", ".tsv", ".md", ".json", ".xml"}


async def parse_plain_text(
    staged: StagedDocument,
    *,
    include_elements: bool,
) -> ParsedDocument:
    def read_text() -> str:
        with open(staged.path, "rb") as rfh:
            return rfh.read().decode("utf-8", errors="replace")

    text = await asyncio.to_thread(read_text)
    if not text.strip():
        raise ValueError("Document produced no extractable text")
    return parsed_document_from_text(
        text,
        suffix=staged.suffix,
        include_elements=include_elements,
    )
