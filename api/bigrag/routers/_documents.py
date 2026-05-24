from __future__ import annotations

import json

__all__ = [
    "parse_form_metadata",
]


def parse_form_metadata(raw_metadata: str) -> dict:
    try:
        parsed = json.loads(raw_metadata) if raw_metadata else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
