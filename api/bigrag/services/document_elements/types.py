from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

ELEMENT_TEXT_LIMIT = 8000
ELEMENT_REF_TEXT_LIMIT = 1200
CONTEXT_RADIUS = 600
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
VALID_KINDS = {"text", "heading", "table", "image", "equation", "unknown"}
ENRICHABLE_KINDS = {"image", "table", "equation"}
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
MATH_BLOCK_RE = re.compile(r"^\s*(\$\$|\\\[|\\begin\{equation\})", re.DOTALL)


@dataclass
class DocumentElementPayload:
    element_index: int
    kind: str
    text: str = ""
    summary: str | None = None
    caption: str | None = None
    page_no: int | None = None
    bbox: dict | list | None = None
    char_start: int | None = None
    char_end: int | None = None
    surrounding_context: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    text: str
    elements: list[DocumentElementPayload] = field(default_factory=list)


def element_asset_prefix_for_file_path(file_path: str) -> str:
    stem = file_path.rsplit(".", 1)[0] if "." in file_path.rsplit("/", 1)[-1] else file_path
    return f"{stem}/elements/"


def _valid_kind(kind: str) -> str:
    return kind if kind in VALID_KINDS else "unknown"


def _surrounding_context(text: str, start: int | None, end: int | None) -> str | None:
    if start is None or end is None:
        return None
    left = max(0, start - CONTEXT_RADIUS)
    right = min(len(text), end + CONTEXT_RADIUS)
    context = text[left:right].strip()
    return context or None


def _element(
    index: int,
    *,
    kind: str,
    text: str = "",
    summary: str | None = None,
    caption: str | None = None,
    page_no: int | None = None,
    bbox: dict | list | None = None,
    char_start: int | None = None,
    char_end: int | None = None,
    surrounding_context: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> DocumentElementPayload:
    return DocumentElementPayload(
        element_index=index,
        kind=_valid_kind(kind),
        text=(text or "")[:ELEMENT_TEXT_LIMIT],
        summary=summary,
        caption=caption,
        page_no=page_no,
        bbox=bbox,
        char_start=char_start,
        char_end=char_end,
        surrounding_context=surrounding_context,
        metadata=metadata or {},
    )
