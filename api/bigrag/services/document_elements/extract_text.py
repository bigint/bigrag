from __future__ import annotations

from bigrag.services.document_elements.types import (
    CONTEXT_RADIUS,
    ELEMENT_TEXT_LIMIT,
    IMAGE_EXTS,
    IMAGE_RE,
    MATH_BLOCK_RE,
    DocumentElementPayload,
    ParsedDocument,
    _element,
    _surrounding_context,
)


def parsed_document_from_text(
    text: str,
    *,
    suffix: str,
    include_elements: bool = False,
) -> ParsedDocument:
    if not include_elements:
        return ParsedDocument(text=text, elements=[])
    return ParsedDocument(
        text=text,
        elements=extract_text_elements(text, suffix=suffix),
    )


def extract_text_elements(
    text: str,
    *,
    suffix: str,
) -> list[DocumentElementPayload]:
    elements: list[DocumentElementPayload] = []
    cursor = 0
    if suffix in IMAGE_EXTS:
        elements.append(
            _element(
                0,
                kind="image",
                text=text[:ELEMENT_TEXT_LIMIT],
                char_start=0 if text else None,
                char_end=len(text) if text else None,
                surrounding_context=text[: CONTEXT_RADIUS * 2] if text else None,
                metadata={"source": "upload"},
            )
        )
    for raw_block in text.split("\n\n"):
        block = raw_block.strip()
        if not block:
            cursor += len(raw_block) + 2
            continue
        start = text.find(raw_block, cursor)
        if start < 0:
            start = cursor
        leading = len(raw_block) - len(raw_block.lstrip())
        char_start = start + leading
        char_end = char_start + len(block)
        kind, caption = _classify_text_block(block)
        elements.append(
            _element(
                len(elements),
                kind=kind,
                text=block,
                caption=caption,
                char_start=char_start,
                char_end=char_end,
                surrounding_context=_surrounding_context(text, char_start, char_end),
                metadata={"source": "text"},
            )
        )
        cursor = start + len(raw_block) + 2
    if not elements and text.strip():
        elements.append(
            _element(
                0,
                kind="text",
                text=text.strip(),
                char_start=text.find(text.strip()),
                char_end=text.find(text.strip()) + len(text.strip()),
                surrounding_context=text[: CONTEXT_RADIUS * 2],
                metadata={"source": "text"},
            )
        )
    return elements


def _classify_text_block(block: str) -> tuple[str, str | None]:
    image = IMAGE_RE.search(block)
    if image:
        return "image", image.group(1).strip() or None
    if block.startswith("#"):
        return "heading", block.lstrip("#").strip()[:1000] or None
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if any(
        first.count("|") >= 2 and second.count("|") >= 2
        for first, second in zip(lines, lines[1:], strict=False)
    ):
        return "table", None
    if (
        MATH_BLOCK_RE.search(block)
        or _looks_like_equation(block)
        or any(_looks_like_equation(line) for line in lines)
    ):
        return "equation", None
    return "text", None


def _looks_like_equation(block: str) -> bool:
    compact = block.strip()
    if len(compact) > 500 or "\n" in compact:
        return False
    markers = ("=", "\\frac", "\\sum", "\\int", "\\le", "\\ge", "^", "_")
    return any(marker in compact for marker in markers) and any(c.isalpha() for c in compact)
