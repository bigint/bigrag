from __future__ import annotations

from bigrag.db.models import Document
from bigrag.services import metadata_schema
from bigrag.services.tenant_enforcement import (
    enforce_document_tenant_access,
    require_tenant_metadata,
)


def prepare_document_metadata(collection: dict, metadata: dict) -> dict:
    metadata_schema.validate(metadata, collection.get("metadata_schema"))
    require_tenant_metadata(collection, metadata)
    return metadata


def check_document_tenant(user: dict, doc: Document, collection: dict) -> None:
    enforce_document_tenant_access(user, collection, doc.meta)
