"""Shared row-to-model converters to eliminate duplication across routers."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


def row_to_model[T: BaseModel](
    row: dict,
    model_class: type[T],
    *,
    exclude: set[str] | None = None,
    transforms: dict[str, callable] | None = None,
) -> T:
    """Convert a database row dict to a Pydantic model.

    - UUIDs are automatically converted to strings.
    - Keys in `exclude` are dropped.
    - Keys in `transforms` have the callable applied to their value.
    """
    data = {}
    for k, v in row.items():
        if exclude and k in exclude:
            continue
        if transforms and k in transforms:
            v = transforms[k](v)
        elif isinstance(v, UUID):
            v = str(v)
        data[k] = v
    return model_class(**data)
