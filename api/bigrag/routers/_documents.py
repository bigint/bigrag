from __future__ import annotations

import json

from bigrag.services.document_progress import document_progress_response
from bigrag.services.documents import check_document_tenant, document_response

__all__ = [
    "check_document_tenant",
    "document_progress_response",
    "document_response",
    "parse_form_metadata",
]


def parse_form_metadata(raw_metadata: str) -> dict:
    try:
        parsed = json.loads(raw_metadata) if raw_metadata else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
