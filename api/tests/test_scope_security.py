from __future__ import annotations

from bigrag.services.scopes import has_scope, required_scope, validate_scope_string


def test_raw_vector_routes_require_vector_scopes() -> None:
    assert required_scope("POST", "/v1/collections/docs/vectors/upsert") == "vector:write"
    assert required_scope("POST", "/v1/collections/docs/vectors/delete") == "vector:delete"


def test_vector_scope_is_valid_and_collection_write_does_not_match() -> None:
    validate_scope_string("vector:write")
    validate_scope_string("vector:delete")

    assert has_scope(["collection:write"], "vector:write") is False
    assert has_scope(["vector:write"], "vector:write") is True
