from __future__ import annotations

from bigrag.routers.mcp_servers import _permissions
from bigrag.services.scopes import has_scope, required_scope, validate_scope_string


def test_raw_vector_routes_require_vector_scopes() -> None:
    assert required_scope("POST", "/v1/collections/docs/vectors/upsert") == "vector:write"
    assert required_scope("POST", "/v1/collections/docs/vectors/delete") == "vector:delete"


def test_vector_scope_is_valid_and_collection_write_does_not_match() -> None:
    validate_scope_string("vector:write")
    validate_scope_string("vector:delete")

    assert has_scope(["collection:write"], "vector:write") is False
    assert has_scope(["vector:write"], "vector:write") is True


def test_collection_events_require_collection_read_scope() -> None:
    assert required_scope("GET", "/v1/collections/docs/events") == "collection:read"
    assert required_scope("POST", "/v1/collections/docs/events/token") == "collection:read"


def test_mcp_permissions_are_read_query_only_by_default() -> None:
    permissions = _permissions("Docs", "docs", None)

    assert permissions["scopes"] == ["collection:read", "document:read", "query:read"]
    assert has_scope(permissions["scopes"], "document:upload") is False
    assert has_scope(permissions["scopes"], "document:delete") is False
    assert has_scope(permissions["scopes"], "vector:write") is False
    assert has_scope(permissions["scopes"], "vector:delete") is False
