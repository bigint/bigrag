from __future__ import annotations

from bigrag.services.document_elements.extract_text import (
    _classify_text_block,
    extract_text_elements,
)
from bigrag.services.document_elements.types import (
    CONTEXT_RADIUS,
    ELEMENT_TEXT_LIMIT,
    IMAGE_EXTS,
    DocumentElementPayload,
    ParsedDocument,
    _element,
    _surrounding_context,
)


def parsed_document_from_docling_result(
    result: object,
    *,
    suffix: str,
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
    )
    if not elements:
        elements = extract_text_elements(text, suffix=suffix)
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
) -> list[DocumentElementPayload]:
    if doc is None:
        return []
    items = _docling_items(doc)
    elements: list[DocumentElementPayload] = []
    cursor = 0
    for item in items:
        kind = _docling_kind(item)
        text = _docling_item_text(item, doc)
        classified_kind, classified_caption = _classify_text_block(text)
        if kind in {"text", "unknown"} and classified_kind != "text":
            kind = classified_kind
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
                char_start=0 if full_text else None,
                char_end=len(full_text) if full_text else None,
                surrounding_context=full_text[: CONTEXT_RADIUS * 2] if full_text else None,
                metadata={"source": "upload"},
            ),
        )
        for index, element in enumerate(elements):
            element.element_index = index
    return elements


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


def _label_value(label: object) -> str:
    value = getattr(label, "value", label)
    return str(value or "").lower()


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
