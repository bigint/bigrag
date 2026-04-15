"""Enforce per-request collection pinning for scoped API keys.

A key with ``permissions.collection = "runbooks"`` is only allowed to
operate on the ``runbooks`` collection. Cross-collection endpoints
(multi-query, batch-query, collection list/create) are blocked outright
— the MCP server already hides them in scoped mode, but we defend the
HTTP API too in case the key is used directly.

This runs *after* scope enforcement in ``get_current_user``. It raises
``HTTPException(403)`` on mismatch; endpoints that naturally scope to a
single collection and match the pin pass through unchanged.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

# Endpoints that operate on multiple collections at once. A scoped key
# can never use these — they'd leak out of the pinned collection.
_FORBIDDEN_FOR_SCOPED: tuple[tuple[str, str], ...] = (
    ("POST", "/v1/query"),
    ("POST", "/v1/batch/query"),
    ("POST", "/v1/collections"),
    # Listing collections leaks names of other collections. Block it;
    # the client can call get_collection({pinned}) instead.
    ("GET", "/v1/collections"),
)


def _extract_collection_name(path: str) -> str | None:
    """Return the collection name from a `/v1/collections/{name}/...`
    path, or None if the path doesn't match."""
    parts = path.strip("/").split("/")
    if len(parts) < 3:
        return None
    if parts[0] != "v1" or parts[1] != "collections":
        return None
    return parts[2]


async def enforce_collection_scope(request: Request, pinned: str) -> None:
    method = request.method
    path = request.url.path

    # Exact match on /v1/collections (no sub-resource) — blocked.
    if (method, path.rstrip("/")) in {(m, p) for m, p in _FORBIDDEN_FOR_SCOPED}:
        raise HTTPException(
            status_code=403,
            detail=(
                f"This API key is pinned to collection {pinned!r} and cannot "
                "use cross-collection endpoints."
            ),
        )

    # Path-scoped endpoint: /v1/collections/{name}/...
    target = _extract_collection_name(path)
    if target is not None and target != pinned:
        raise HTTPException(
            status_code=403,
            detail=(
                f"This API key is pinned to collection {pinned!r}; request "
                f"targeted {target!r}."
            ),
        )
