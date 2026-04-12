"""Tests for PII redaction, moderation, metadata schema, and evaluation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bigrag.services import metadata_schema, pii
from bigrag.services.retrieval import RetrievalOutcome


class TestPII:
    def test_redacts_emails(self):
        out = pii.redact("Contact me at foo@bar.com for details.")
        assert "[EMAIL]" in out
        assert "foo@bar.com" not in out

    def test_redacts_phone_numbers(self):
        for phone in ("+1-555-123-4567", "(555) 123-4567", "555.123.4567"):
            out = pii.redact(f"Call {phone}")
            assert "[PHONE]" in out, f"failed for {phone}"

    def test_redacts_ssn(self):
        assert "[SSN]" in pii.redact("SSN 123-45-6789 verified")

    def test_redacts_card_with_luhn(self):
        # 4242 4242 4242 4242 is a valid test card (passes Luhn)
        assert "[CARD]" in pii.redact("Pay with 4242 4242 4242 4242")

    def test_random_16_digit_not_luhn_valid_is_kept(self):
        # 9876543210987654 does not pass Luhn.
        out = pii.redact("Reference 9876543210987654 in the ledger")
        assert "9876543210987654" in out  # unchanged
        assert "[CARD]" not in out

    def test_has_pii_reports_presence(self):
        assert pii.has_pii("email foo@bar.com") is True
        assert pii.has_pii("nothing sensitive") is False


class TestMetadataSchema:
    def test_passes_valid_metadata(self):
        schema = {
            "type": "object",
            "required": ["owner"],
            "properties": {
                "owner": {"type": "string", "minLength": 1},
                "priority": {"type": "integer", "minimum": 0, "maximum": 10},
                "tier": {"type": "string", "enum": ["free", "pro"]},
            },
        }
        metadata_schema.validate({"owner": "alice", "priority": 5, "tier": "pro"}, schema)

    def test_rejects_missing_required(self):
        schema = {"type": "object", "required": ["owner"]}
        with pytest.raises(ValueError, match="missing required field"):
            metadata_schema.validate({}, schema)

    def test_rejects_wrong_type(self):
        schema = {"properties": {"n": {"type": "integer"}}}
        with pytest.raises(ValueError, match="must be integer"):
            metadata_schema.validate({"n": "not-a-number"}, schema)

    def test_rejects_out_of_enum(self):
        schema = {"properties": {"env": {"enum": ["dev", "prod"]}}}
        with pytest.raises(ValueError, match="must be one of"):
            metadata_schema.validate({"env": "staging"}, schema)

    def test_rejects_pattern_mismatch(self):
        schema = {"properties": {"sku": {"type": "string", "pattern": r"^[A-Z]{3}-\d+$"}}}
        with pytest.raises(ValueError, match="must match pattern"):
            metadata_schema.validate({"sku": "lowercase-123"}, schema)

    def test_none_schema_is_noop(self):
        metadata_schema.validate({"anything": "goes"}, None)


class TestEvaluation:
    @pytest.mark.asyncio
    async def test_evaluation_computes_recall_mrr_ndcg(
        self, client, auth_headers, mock_db
    ):
        from tests.conftest import install_fetchrow_router, make_collection_row

        install_fetchrow_router(
            mock_db,
            lambda q, *a: make_collection_row("eval_col")
            if "FROM collections" in q
            else None,
        )

        # Two cases. Case 1: expected doc-1, top hit is doc-1 (perfect).
        # Case 2: expected doc-9, top hit is doc-other (miss).
        def _outcome_for(query: str) -> RetrievalOutcome:
            if "one" in query:
                return RetrievalOutcome(
                    results=[
                        {"id": "c1", "document_id": "doc-1", "score": 0.9},
                        {"id": "c2", "document_id": "doc-2", "score": 0.7},
                    ],
                    total_ms=10.0,
                )
            return RetrievalOutcome(
                results=[{"id": "c3", "document_id": "doc-other", "score": 0.5}],
                total_ms=12.0,
            )

        async def fake_retrieve(**kwargs):
            return _outcome_for(kwargs["query"])

        with (
            patch(
                "bigrag.routers.evaluation.get_embedding_model_for",
                return_value=MagicMock(),
            ),
            patch(
                "bigrag.routers.evaluation.get_reranking_config",
                return_value={"enabled": False, "model": "x", "api_key": None},
            ),
            patch(
                "bigrag.routers.evaluation.retrieve",
                new_callable=AsyncMock,
                side_effect=fake_retrieve,
            ),
        ):
            resp = await client.post(
                "/v1/evaluation",
                headers=auth_headers,
                json={
                    "collection": "eval_col",
                    "cases": [
                        {"query": "case one", "relevant_ids": ["doc-1"]},
                        {"query": "case two", "relevant_ids": ["doc-9"]},
                    ],
                    "top_k": 5,
                },
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_cases"] == 2
        # Case 1 recall = 1 (perfect), case 2 recall = 0; average = 0.5
        assert body["recall_at_k_avg"] == pytest.approx(0.5, abs=0.01)
        # Case 1 rr = 1/1 = 1, case 2 = 0; average = 0.5
        assert body["mrr"] == pytest.approx(0.5, abs=0.01)
