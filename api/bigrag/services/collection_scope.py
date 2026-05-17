from __future__ import annotations

from fastapi import Request

from bigrag.exceptions import ForbiddenError

_FORBIDDEN_FOR_SCOPED: tuple[tuple[str, str], ...] = (
    ("POST", "/v1/query"),
    ("POST", "/v1/batch/query"),
    ("POST", "/v1/collections"),
    ("PUT", "/v1/collections/"),
    ("DELETE", "/v1/collections/"),
    ("GET", "/v1/collections"),
    ("GET", "/v1/usage"),
    ("GET", "/v1/stats"),
    ("GET", "/v1/embeddings/models"),
)

_FORBIDDEN_METHODS_ON_PINNED_COLLECTION = frozenset({"PUT", "DELETE"})
_FORBIDDEN_FOR_SCOPED_SET = frozenset(_FORBIDDEN_FOR_SCOPED)


def _extract_collection_name(path: str) -> str | None:

    parts = path.strip("/").split("/")
    if len(parts) < 3:
        return None
    if parts[0] != "v1" or parts[1] != "collections":
        return None
    return parts[2]


def assert_collection_matches_pin(pinned: str, target: str) -> None:
    if target != pinned:
        raise ForbiddenError(
            f"This API key is pinned to collection {pinned!r}; request targeted {target!r}."
        )


async def enforce_collection_scope(request: Request, pinned: str) -> None:
    method = request.method
    path = request.url.path
    stripped = path.rstrip("/")

    if (method, stripped) in _FORBIDDEN_FOR_SCOPED_SET:
        raise ForbiddenError(
            f"This API key is pinned to collection {pinned!r} and cannot "
            "use cross-collection endpoints."
        )

    target = _extract_collection_name(path)
    if target is not None:
        assert_collection_matches_pin(pinned, target)

    parts = stripped.strip("/").split("/")
    is_collection_root = (len(parts) == 3 and parts[0] == "v1" and parts[1] == "collections") or (
        len(parts) == 2 and parts[1] == "collections"
    )
    if is_collection_root and method in _FORBIDDEN_METHODS_ON_PINNED_COLLECTION:
        raise ForbiddenError(
            f"This API key is pinned to collection {pinned!r}; reconfiguring or "
            "deleting collections is not allowed."
        )
