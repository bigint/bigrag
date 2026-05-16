from __future__ import annotations

from bigrag.db.models import AccessLog, Document


def test_document_indexes_include_collection_sorted_list_shapes() -> None:
    names = {index.name for index in Document.__table__.indexes}

    assert "idx_documents_collection_created_at" in names
    assert "idx_documents_collection_status_created_at" in names


def test_access_log_indexes_include_sorted_filter_shapes() -> None:
    names = {index.name for index in AccessLog.__table__.indexes}

    assert "idx_access_log_actor_created_at" in names
    assert "idx_access_log_action_created_at" in names
    assert "idx_access_log_collection_created_at" in names
