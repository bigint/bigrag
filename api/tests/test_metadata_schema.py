from __future__ import annotations

import pytest

from bigrag.services import metadata_schema


def test_validate_accepts_required_typed_metadata() -> None:
    schema = {
        "type": "object",
        "required": ["tenant_id", "year"],
        "properties": {
            "tenant_id": {"type": "string", "pattern": r"[a-z0-9_-]+"},
            "year": {"type": "integer", "minimum": 2020},
        },
    }

    metadata_schema.validate({"tenant_id": "acme_1", "year": 2026}, schema)


def test_validate_rejects_missing_required_metadata() -> None:
    schema = {"type": "object", "required": ["tenant_id"]}

    with pytest.raises(ValueError, match="tenant_id"):
        metadata_schema.validate({}, schema)


def test_validate_rejects_wrong_metadata_type() -> None:
    schema = {"type": "object", "properties": {"public": {"type": "boolean"}}}

    with pytest.raises(ValueError, match="boolean"):
        metadata_schema.validate({"public": "yes"}, schema)
