from __future__ import annotations

from starlette.requests import Request

from bigrag.services.access_log import (
    _infer_action,
    _safe_metadata,
    _should_record,
    filter_summary,
    query_fingerprint,
    set_context,
)


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/v1/query",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
        }
    )


def test_query_fingerprint_does_not_store_raw_query() -> None:
    fp = query_fingerprint("what is the launch code?")

    assert fp["query_length"] == 24
    assert fp["query_hash"] != "what is the launch code?"
    assert len(str(fp["query_hash"])) == 24


def test_infer_query_actions_uses_specific_routes_first() -> None:
    assert _infer_action("POST", "/v1/query") == ("query.multi", "collections")
    assert _infer_action("POST", "/v1/batch/query") == ("query.batch", "collections")
    assert _infer_action("POST", "/v1/collections/docs/query") == ("query.run", "collection")
    assert _infer_action("POST", "/v1/evaluation") == ("evaluation.run", "collection")


def test_should_record_only_rag_access_routes() -> None:
    assert _should_record({"type": "http", "method": "POST", "path": "/v1/query"})
    assert _should_record({"type": "http", "method": "POST", "path": "/v1/collections/docs/query"})
    assert _should_record(
        {"type": "http", "method": "POST", "path": "/v1/collections/docs/vectors/upsert"}
    )
    assert _should_record({"type": "http", "method": "POST", "path": "/v1/evaluation"})
    assert not _should_record({"type": "http", "method": "GET", "path": "/v1/auth/me"})
    assert not _should_record({"type": "http", "method": "GET", "path": "/v1/collections"})
    assert not _should_record(
        {"type": "http", "method": "GET", "path": "/v1/admin/access/overview"}
    )
    assert not _should_record({"type": "http", "method": "POST", "path": "/mcp"})


def test_filter_summary_reports_keys_only() -> None:
    summary = filter_summary({"tenant_id": "acme", "department": {"$eq": "research"}})

    assert summary == {"has_filters": True, "filter_keys": ["department", "tenant_id"]}


def test_safe_metadata_redacts_sensitive_values() -> None:
    safe = _safe_metadata(
        {
            "query": "raw user question",
            "token": "secret-token",
            "top_k": 10,
            "nested": {"api_key": "bigrag_xxx"},
        }
    )

    assert safe["query"] == "[REDACTED]"
    assert safe["token"] == "[REDACTED]"
    assert safe["nested"] == {"api_key": "[REDACTED]"}
    assert safe["top_k"] == 10


def test_set_context_merges_metadata() -> None:
    request = _request()

    set_context(request, action="query.run", metadata={"top_k": 5})
    set_context(request, collection_name="docs", metadata={"result_count": 3})

    assert request.state.access_log_context == {
        "action": "query.run",
        "collection_name": "docs",
        "metadata": {"top_k": 5, "result_count": 3},
    }
