from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from bigrag.db.models import Document, DocumentElement

ELEMENT_TEXT_LIMIT = 8000
ELEMENT_REF_TEXT_LIMIT = 1200
CONTEXT_RADIUS = 600
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
VALID_KINDS = {"text", "heading", "table", "image", "equation", "unknown"}
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
MATH_BLOCK_RE = re.compile(r"^\s*(\$\$|\\\[|\\begin\{equation\})", re.DOTALL)


@dataclass
class DocumentElementPayload:
    element_index: int
    kind: str
    text: str = ""
    summary: str | None = None
    caption: str | None = None
    asset_path: str | None = None
    asset_bytes: bytes | None = None
    asset_media_type: str | None = None
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


def parsed_document_from_text(
    text: str,
    *,
    suffix: str,
    source_asset_path: str | None = None,
    include_elements: bool = False,
) -> ParsedDocument:
    if not include_elements:
        return ParsedDocument(text=text, elements=[])
    return ParsedDocument(
        text=text,
        elements=extract_text_elements(text, suffix=suffix, source_asset_path=source_asset_path),
    )


def parsed_document_from_docling_result(
    result: object,
    *,
    suffix: str,
    source_asset_path: str | None,
    include_elements: bool,
) -> ParsedDocument:
    text = docling_result_text(result)
    if not include_elements:
        return ParsedDocument(text=text, elements=[])
    doc = getattr(result, "document", None)
    elements = extract_docling_elements(
        doc,
        text,
        suffix=suffix,
        source_asset_path=source_asset_path,
    )
    if not elements:
        elements = extract_text_elements(text, suffix=suffix, source_asset_path=source_asset_path)
    return ParsedDocument(text=text, elements=elements)


def docling_result_text(result: object) -> str:
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


def extract_docling_elements(
    doc: object | None,
    full_text: str,
    *,
    suffix: str,
    source_asset_path: str | None,
) -> list[DocumentElementPayload]:
    if doc is None:
        return []
    items = _docling_items(doc)
    elements: list[DocumentElementPayload] = []
    cursor = 0
    for item in items:
        kind = _docling_kind(item)
        text = _docling_item_text(item, doc)
        classified_kind, classified_caption, classified_asset_path = _classify_text_block(text)
        if kind in {"text", "unknown"} and classified_kind != "text":
            kind = classified_kind
        asset_path = _docling_asset_path(item)
        asset_bytes, asset_media_type = _docling_asset_bytes(item, doc)
        if not asset_path:
            asset_path = classified_asset_path
        if kind == "image" and not asset_path and suffix in IMAGE_EXTS:
            asset_path = source_asset_path
        if not text and kind not in {"image", "table", "equation"}:
            continue
        char_start, char_end, cursor = _find_span(full_text, text, cursor)
        page_no, bbox = _docling_provenance(item)
        elements.append(
            _element(
                len(elements),
                kind=kind,
                text=text,
                caption=_caption_for(item, text) or classified_caption,
                asset_path=asset_path,
                asset_bytes=asset_bytes,
                asset_media_type=asset_media_type,
                page_no=page_no,
                bbox=bbox,
                char_start=char_start,
                char_end=char_end,
                surrounding_context=_surrounding_context(full_text, char_start, char_end),
                metadata={"source": "docling", "label": _label_value(getattr(item, "label", None))},
            )
        )
    if suffix in IMAGE_EXTS and not any(element.kind == "image" for element in elements):
        elements.insert(
            0,
            _element(
                0,
                kind="image",
                text=full_text[:ELEMENT_TEXT_LIMIT],
                asset_path=source_asset_path,
                char_start=0 if full_text else None,
                char_end=len(full_text) if full_text else None,
                surrounding_context=full_text[: CONTEXT_RADIUS * 2] if full_text else None,
                metadata={"source": "upload"},
            ),
        )
        for index, element in enumerate(elements):
            element.element_index = index
    return elements


def extract_text_elements(
    text: str,
    *,
    suffix: str,
    source_asset_path: str | None,
) -> list[DocumentElementPayload]:
    elements: list[DocumentElementPayload] = []
    cursor = 0
    if suffix in IMAGE_EXTS:
        elements.append(
            _element(
                0,
                kind="image",
                text=text[:ELEMENT_TEXT_LIMIT],
                asset_path=source_asset_path,
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
        kind, caption, asset_path = _classify_text_block(block)
        if asset_path is None and kind == "image" and suffix in IMAGE_EXTS:
            asset_path = source_asset_path
        elements.append(
            _element(
                len(elements),
                kind=kind,
                text=block,
                caption=caption,
                asset_path=asset_path,
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


async def replace_document_elements(
    session: AsyncSession,
    *,
    document_id: uuid.UUID,
    elements: list[DocumentElementPayload],
    enrichment_enabled: bool,
) -> int:
    document = await session.get(Document, document_id)
    if document is None:
        return 0
    await session.execute(
        sa.delete(DocumentElement).where(DocumentElement.document_id == document_id)
    )
    from bigrag.services.storage import get_storage

    storage = get_storage()
    asset_prefix = element_asset_prefix_for_file_path(document.file_path)
    await storage.delete_prefix(asset_prefix)
    rows = []
    for index, element in enumerate(elements):
        asset_path = element.asset_path
        if element.asset_bytes:
            asset_path = f"{asset_prefix}{index}{_asset_suffix(element.asset_media_type)}"
            await storage.put(asset_path, element.asset_bytes)
        rows.append(
            DocumentElement(
                document_id=document_id,
                collection_id=document.collection_id,
                element_index=index,
                kind=_valid_kind(element.kind),
                text=element.text[:ELEMENT_TEXT_LIMIT],
                summary=element.summary,
                caption=element.caption,
                asset_path=asset_path,
                page_no=element.page_no,
                bbox=element.bbox,
                char_start=element.char_start,
                char_end=element.char_end,
                surrounding_context=element.surrounding_context,
                meta=element.metadata,
                enrichment_status=_enrichment_status(element, enrichment_enabled),
            )
        )
    session.add_all(rows)
    document.multimodal_element_count = len(rows)
    await session.flush()
    return len(rows)


def element_refs_for_chunk(
    elements: list[DocumentElementPayload],
    *,
    document_id: str,
    chunk_start: int,
    chunk_end: int,
    chunk_index: int,
) -> list[dict[str, Any]]:
    refs = []
    for element in elements:
        if element.kind == "text":
            continue
        if not _element_overlaps_chunk(element, chunk_start, chunk_end, chunk_index):
            continue
        refs.append(element_ref(element, document_id=document_id))
        if len(refs) >= 8:
            break
    return refs


def element_ref(
    element: DocumentElementPayload | DocumentElement, *, document_id: str | None
) -> dict[str, Any]:
    text = getattr(element, "summary", None) or getattr(element, "text", "")
    metadata = getattr(element, "meta", None)
    if metadata is None:
        metadata = getattr(element, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "document_id": document_id,
        "element_index": int(element.element_index),
        "kind": _valid_kind(str(getattr(element, "kind", "unknown"))),
        "text": str(text or "")[:ELEMENT_REF_TEXT_LIMIT],
        "summary": getattr(element, "summary", None),
        "caption": getattr(element, "caption", None),
        "asset_path": getattr(element, "asset_path", None),
        "page_no": getattr(element, "page_no", None),
        "bbox": getattr(element, "bbox", None),
        "metadata": dict(metadata),
    }


def _docling_items(doc: object) -> list[object]:
    iterator = getattr(doc, "iterate_items", None)
    if callable(iterator):
        try:
            return [item for item, _level in iterator()]
        except Exception:
            pass
    items = []
    for attr in ("texts", "tables", "pictures", "key_value_items", "form_items"):
        value = getattr(doc, attr, None)
        if isinstance(value, list):
            items.extend(value)
    return items


def _docling_kind(item: object) -> str:
    label = _label_value(getattr(item, "label", None))
    if label in {"title", "section_header", "heading"}:
        return "heading"
    if "table" in label:
        return "table"
    if label in {"picture", "figure", "image"}:
        return "image"
    if "formula" in label or "equation" in label:
        return "equation"
    if label == "text":
        return "text"
    return "unknown"


def _docling_item_text(item: object, doc: object) -> str:
    raw = getattr(item, "text", None) or getattr(item, "orig", None)
    if raw:
        return str(raw).strip()
    for method in ("export_to_markdown", "export_to_text", "export_to_html"):
        fn = getattr(item, method, None)
        if not callable(fn):
            continue
        for args in ((doc,), ()):
            try:
                value = fn(*args)
            except TypeError:
                continue
            except Exception:
                break
            if value:
                return str(value).strip()
    return ""


def _docling_asset_path(item: object) -> str | None:
    dump = _jsonable(item)
    if not isinstance(dump, dict):
        return None
    stack = [dump]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if key in {"uri", "path", "img_path", "image_path"} and isinstance(value, str):
                    candidate = _stored_asset_path_candidate(value)
                    if candidate:
                        return candidate
                if isinstance(value, dict | list):
                    stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
    return None


def _docling_asset_bytes(item: object, doc: object) -> tuple[bytes | None, str | None]:
    image = None
    for method_name in ("get_image", "get_pil_image"):
        method = getattr(item, method_name, None)
        if not callable(method):
            continue
        for args in ((doc,), ()):
            try:
                image = method(*args)
            except TypeError:
                continue
            except Exception:
                image = None
                break
            if image is not None:
                break
        if image is not None:
            break
    if image is None:
        image = getattr(item, "image", None)
    if image is None:
        return None, None
    save = getattr(image, "save", None)
    if callable(save):
        buffer = BytesIO()
        save(buffer, format="PNG")
        return buffer.getvalue(), "image/png"
    data = getattr(image, "data", None)
    if isinstance(data, bytes):
        return data, getattr(image, "mime_type", None) or "image/png"
    return None, None


def _docling_provenance(item: object) -> tuple[int | None, dict | list | None]:
    prov = getattr(item, "prov", None)
    if not prov:
        return None, None
    first = prov[0]
    page_no = getattr(first, "page_no", None)
    bbox = _jsonable(getattr(first, "bbox", None))
    return page_no, bbox if isinstance(bbox, dict | list) else None


def _caption_for(item: object, fallback: str) -> str | None:
    for attr in ("caption", "name"):
        value = getattr(item, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()[:1000]
    if _docling_kind(item) == "heading":
        return fallback[:1000] or None
    return None


def _classify_text_block(block: str) -> tuple[str, str | None, str | None]:
    image = IMAGE_RE.search(block)
    if image:
        asset_path = _stored_asset_path_candidate(image.group(2))
        return "image", image.group(1).strip() or None, asset_path
    if block.startswith("#"):
        return "heading", block.lstrip("#").strip()[:1000] or None, None
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    if any(
        first.count("|") >= 2 and second.count("|") >= 2
        for first, second in zip(lines, lines[1:], strict=False)
    ):
        return "table", None, None
    if (
        MATH_BLOCK_RE.search(block)
        or _looks_like_equation(block)
        or any(_looks_like_equation(line) for line in lines)
    ):
        return "equation", None, None
    return "text", None, None


def _looks_like_equation(block: str) -> bool:
    compact = block.strip()
    if len(compact) > 500 or "\n" in compact:
        return False
    markers = ("=", "\\frac", "\\sum", "\\int", "\\le", "\\ge", "^", "_")
    return any(marker in compact for marker in markers) and any(c.isalpha() for c in compact)


def _find_span(full_text: str, text: str, cursor: int) -> tuple[int | None, int | None, int]:
    needle = text.strip()
    if not needle:
        return None, None, cursor
    index = full_text.find(needle, cursor)
    if index < 0:
        index = full_text.find(needle)
    if index < 0:
        return None, None, cursor
    end = index + len(needle)
    return index, end, end


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
    asset_path: str | None = None,
    asset_bytes: bytes | None = None,
    asset_media_type: str | None = None,
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
        asset_path=asset_path,
        asset_bytes=asset_bytes,
        asset_media_type=asset_media_type,
        page_no=page_no,
        bbox=bbox,
        char_start=char_start,
        char_end=char_end,
        surrounding_context=surrounding_context,
        metadata=metadata or {},
    )


def _element_overlaps_chunk(
    element: DocumentElementPayload,
    chunk_start: int,
    chunk_end: int,
    chunk_index: int,
) -> bool:
    if element.char_start is None or element.char_end is None:
        return chunk_index == 0
    return element.char_start < chunk_end and element.char_end > chunk_start


def _enrichment_status(element: DocumentElementPayload, enrichment_enabled: bool) -> str:
    if enrichment_enabled and element.kind in {"image", "table", "equation"}:
        return "pending"
    return "not_requested"


def element_asset_prefix_for_file_path(file_path: str) -> str:
    stem = file_path.rsplit(".", 1)[0] if "." in file_path.rsplit("/", 1)[-1] else file_path
    return f"{stem}/elements/"


def _asset_suffix(media_type: str | None) -> str:
    if media_type == "image/jpeg":
        return ".jpg"
    if media_type == "image/webp":
        return ".webp"
    if media_type == "image/gif":
        return ".gif"
    return ".png"


def _stored_asset_path_candidate(value: str) -> str | None:
    candidate = value.strip()
    if not candidate or candidate.startswith("/") or "://" in candidate:
        return None
    if any(part == ".." for part in candidate.split("/")):
        return None
    return candidate


def _label_value(label: object) -> str:
    value = getattr(label, "value", label)
    return str(value or "").lower()


def _valid_kind(kind: str) -> str:
    return kind if kind in VALID_KINDS else "unknown"


def _jsonable(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str | int | float | bool):
        return enum_value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return _jsonable(dump())
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    return str(value)
