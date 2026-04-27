from __future__ import annotations

from bigrag.services.scopes import required_scope


def test_collection_job_mutations_require_write_or_delete_scope() -> None:
    assert (
        required_scope(
            "PATCH",
            "/v1/collections/demo/s3-jobs/00000000-0000-0000-0000-000000000000",
        )
        == "collection:write"
    )
    assert (
        required_scope(
            "POST",
            "/v1/collections/demo/s3-jobs/00000000-0000-0000-0000-000000000000/resync",
        )
        == "collection:write"
    )
    assert (
        required_scope(
            "DELETE",
            "/v1/collections/demo/s3-jobs/00000000-0000-0000-0000-000000000000",
        )
        == "collection:delete"
    )


def test_evaluation_requires_query_scope() -> None:
    assert required_scope("POST", "/v1/evaluation") == "query:read"


def test_webhook_detail_mutations_are_scoped() -> None:
    assert required_scope("PUT", "/v1/admin/webhooks/wh_123") == "webhook:write"
    assert required_scope("DELETE", "/v1/admin/webhooks/wh_123") == "webhook:write"
    assert required_scope("POST", "/v1/admin/webhooks/wh_123/test") == "webhook:write"
