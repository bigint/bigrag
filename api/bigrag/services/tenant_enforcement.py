from __future__ import annotations

from bigrag.exceptions import ValidationError


def tenant_field(collection: dict) -> str | None:
    value = collection.get("tenant_field")
    return value if isinstance(value, str) and value else None


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
