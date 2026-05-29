from __future__ import annotations

from bigrag.db.models import Document
from bigrag.exceptions import ValidationError
from bigrag.services import metadata_schema
from bigrag.services.tenant_enforcement import (
    enforce_document_tenant_access,
    is_admin_org_global,
    principal_tenant_id,
    require_tenant_metadata,
    tenant_field,
)


def prepare_document_metadata(collection: dict, metadata: dict) -> dict:
    metadata_schema.validate(metadata, collection.get("metadata_schema"))
    require_tenant_metadata(collection, metadata)
    return metadata


def check_document_tenant(user: dict, doc: Document, collection: dict) -> None:
    enforce_document_tenant_access(user, collection, doc.meta)


def document_tenant_metadata_filter(user: dict, collection: dict) -> dict | None:
    field = tenant_field(collection)
    if not field:
        return None
    tenant = principal_tenant_id(user)
    if tenant is not None:
        return {field: tenant}
    if is_admin_org_global(user):
        return None
    raise ValidationError(
        f"This API key is not scoped to a tenant; access to collection "
        f"{collection.get('name')!r} (tenant_field {field!r}) is denied"
    )
