from __future__ import annotations


def _pagination(*, limit: int | None, offset: int | None) -> dict[str, str]:
    params: dict[str, str] = {}
    if limit is not None:
        params["limit"] = str(limit)
    if offset is not None:
        params["offset"] = str(offset)
    return params
