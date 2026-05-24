from __future__ import annotations

from bigrag.exceptions import ValidationError


def tenant_field(collection: dict) -> str | None:
    value = collection.get("tenant_field")
    return value if isinstance(value, str) and value else None


def principal_tenant_id(principal: dict | None) -> str | None:
    if not principal:
        return None
    value = principal.get("tenant_id")
    return value if isinstance(value, str) and value else None


def is_admin_org_global(principal: dict | None) -> bool:
    if not principal:
        return False
    return (
        principal.get("role") == "admin"
        and principal.get("auth_method") != "api_key"
        and not principal.get("collection")
    )


def enforce_tenant_filters(
    collection: dict,
    filters: dict | None,
    principal: dict | None,
) -> dict | None:
    field = tenant_field(collection)
    if not field:
        return filters
    tenant = principal_tenant_id(principal)
    if tenant is not None:
        forced = dict(filters) if isinstance(filters, dict) else {}
        forced[field] = {"$eq": tenant}
        return forced
    if is_admin_org_global(principal):
        return filters
    raise ValidationError(
        f"This API key is not scoped to a tenant; access to collection "
        f"{collection.get('name')!r} (tenant_field {field!r}) is denied"
    )


def document_tenant_allowed(principal: dict, collection: dict, doc_meta: dict | None) -> bool:
    field = tenant_field(collection)
    if not field:
        return True
    if is_admin_org_global(principal):
        return True
    tenant = principal_tenant_id(principal)
    if tenant is None:
        return False
    doc_tenant = (doc_meta or {}).get(field) if doc_meta else None
    return tenant == doc_tenant


def enforce_document_tenant_access(
    principal: dict,
    collection: dict,
    doc_meta: dict | None,
) -> None:
    from fastapi import HTTPException

    if not document_tenant_allowed(principal, collection, doc_meta):
        raise HTTPException(status_code=404, detail="Document not found")


def enforce_tenant_metadata(
    collection: dict,
    metadata: dict,
    principal: dict | None,
    *,
    label: str = "metadata",
) -> dict:
    field = tenant_field(collection)
    if not field:
        return metadata
    tenant = principal_tenant_id(principal)
    if tenant is not None:
        forced = dict(metadata)
        forced[field] = tenant
        return forced
    if is_admin_org_global(principal):
        require_tenant_metadata(collection, metadata, label=label)
        return metadata
    raise ValidationError(
        f"This API key is not scoped to a tenant; writes to collection "
        f"{collection.get('name')!r} (tenant_field {field!r}) are denied"
    )


def require_tenant_metadata(collection: dict, metadata: dict, *, label: str = "metadata") -> None:
    field = tenant_field(collection)
    if not field:
        return
    value = metadata.get(field)
    if value is None or value == "":
        raise ValidationError(
            f"{label}.{field} is required because collection tenant_field is {field!r}"
        )


def require_tenant_filters(collection: dict, filters: dict | None) -> None:
    field = tenant_field(collection)
    if not field:
        return
    if not _has_tenant_filter(field, filters):
        raise ValidationError(
            f"filters.{field} is required because collection tenant_field is {field!r}"
        )


def _has_tenant_filter(field: str, filters: dict | None) -> bool:
    if not isinstance(filters, dict):
        return False
    value = filters.get(field)
    if isinstance(value, (str, int, float, bool)):
        return value != ""
    if isinstance(value, dict):
        if "$eq" in value:
            eq = value.get("$eq")
            return eq is not None and eq != ""
        if "$in" in value:
            items = value.get("$in")
            valid_items = (
                [item for item in items if item is not None and item != ""]
                if isinstance(items, list)
                else []
            )
            return len(valid_items) >= 1
    return False
