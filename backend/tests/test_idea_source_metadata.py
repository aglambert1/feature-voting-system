"""Tests for the opportunity source_metadata builder and the external adapter.

The builder must reproduce the exact shapes the two pre-existing writers
emitted (triage's authoritative readers and the linked-idea backfill script
key on them).
"""

from unittest.mock import MagicMock

import pytest

from app.adapters.external_submission import ExternalSubmissionAdapter
from app.models.idea import SourceType
from app.queue.helpers import _authoritative_competitor_names, _authoritative_job_key
from app.services.idea_source_metadata import build_opportunity_source_metadata


COMPETITIVE_EVIDENCE = {"competitors": ["Comp A", "Comp B"], "prevalence": "2 of 3"}


class TestBuildOpportunitySourceMetadata:
    def test_matches_synthesis_autogen_literal(self):
        # The exact shape synthesis_tasks.py emitted before the builder
        expected = {
            "synthesis_report_id": 7,
            "synthesis_report_version": 3,
            "feature_name": "Custom Dashboards",
            "priority_score": 88,
            "sources": ["competitive", "customer"],
            "job_id_key": "j2",
            "investment_tier": "strategic",
            "competitors_with_feature": ["Comp A", "Comp B"],
            "competitor_names": ["Comp A", "Comp B"],
        }
        built = build_opportunity_source_metadata(
            synthesis_report_id=7,
            report_version=3,
            feature_name="Custom Dashboards",
            priority_score=88,
            sources=["competitive", "customer"],
            job_id_key="j2",
            investment_tier="strategic",
            competitive_evidence=COMPETITIVE_EVIDENCE,
        )
        assert built == expected

    def test_matches_manual_create_literal(self):
        # The exact shape unified_synthesis.py emitted before the builder
        expected = {
            "synthesis_report_id": 7,
            "opportunity_id": 42,
            "feature_name": "Custom Dashboards",
            "priority_score": 88,
            "sources": ["competitive"],
            "job_id_key": "j2",
            "investment_tier": "strategic",
            "manual_creation": True,
            "competitors_with_feature": ["Comp A", "Comp B"],
            "competitor_names": ["Comp A", "Comp B"],
        }
        built = build_opportunity_source_metadata(
            synthesis_report_id=7,
            opportunity_id=42,
            feature_name="Custom Dashboards",
            priority_score=88,
            sources=["competitive"],
            job_id_key="j2",
            investment_tier="strategic",
            competitive_evidence=COMPETITIVE_EVIDENCE,
            manual_creation=True,
        )
        assert built == expected

    def test_authoritative_readers_round_trip(self):
        built = build_opportunity_source_metadata(
            synthesis_report_id=1,
            feature_name="X",
            priority_score=50,
            sources=None,
            job_id_key="j9",
            investment_tier=None,
            competitive_evidence=COMPETITIVE_EVIDENCE,
        )
        assert _authoritative_job_key(built) == "j9"
        assert _authoritative_competitor_names(built) == ["Comp A", "Comp B"]

    def test_empty_competitor_list_stays_authoritative(self):
        # Customer-only opportunity: empty list must read as authoritative-empty,
        # not fall back to the agent's list.
        built = build_opportunity_source_metadata(
            synthesis_report_id=1,
            feature_name="X",
            priority_score=50,
            sources=[],
            job_id_key=None,
            investment_tier=None,
            competitive_evidence=None,
        )
        assert built["competitor_names"] == []
        assert _authoritative_competitor_names(built) == []
        assert _authoritative_job_key(built) is None
        assert built["sources"] == []


class TestExternalSubmissionAdapter:
    def _adapter(self):
        llm = MagicMock()
        adapter = ExternalSubmissionAdapter(db=None, llm_service=llm)
        return adapter, llm

    def _record(self, **overrides):
        record = {
            "product_id": 1,
            "external_id": "AHA-123",
            "external_source": "aha",
            "title": "Better exports",
            "description": "Customers want CSV export of dashboards",
        }
        record.update(overrides)
        return record

    def test_source_type_and_registry(self):
        from app.services.idea_normalizer_service import IdeaNormalizerService

        adapter, _ = self._adapter()
        assert adapter.get_source_type() == SourceType.EXTERNAL_SUBMISSION
        assert IdeaNormalizerService.ADAPTER_REGISTRY[SourceType.EXTERNAL_SUBMISSION] is ExternalSubmissionAdapter

    def test_validate_input_matrix(self):
        adapter, _ = self._adapter()
        assert adapter.validate_input(self._record()) is True
        for missing in ("product_id", "external_id", "external_source", "title", "description"):
            record = self._record()
            record.pop(missing)
            assert adapter.validate_input(record) is False, missing
        assert adapter.validate_input(self._record(title="   ")) is False

    def test_normalize_field_mapping(self):
        adapter, llm = self._adapter()
        normalized = adapter.normalize(self._record(
            why="Reporting workflows",
            use_case="Monthly exec review",
            category="Reporting",
            url="https://co.aha.io/ideas/AHA-123",
            submitter="Jane (customer)",
            vote_count=41,
            external_status="Under consideration",
        ))

        assert normalized.title == "Better exports"
        assert normalized.what_description == "Customers want CSV export of dashboards"
        assert normalized.why_description == "Reporting workflows"
        assert normalized.use_case_description == "Monthly exec review"
        assert normalized.category == "Reporting"
        assert normalized.external_id == "AHA-123"
        assert normalized.external_source == "aha"
        assert normalized.source_type == SourceType.EXTERNAL_SUBMISSION

        metadata = normalized.source_metadata
        assert metadata["external_url"] == "https://co.aha.io/ideas/AHA-123"
        assert metadata["submitter_label"] == "Jane (customer)"
        assert metadata["external_vote_count"] == 41
        assert metadata["external_status"] == "Under consideration"
        assert "imported_at" in metadata
        # No authoritative trigger keys — imports triage like customer ideas
        assert "competitor_name" not in metadata
        assert "competitor_names" not in metadata
        assert "job_id_key" not in metadata

        # Deterministic: no LLM involvement
        llm.structure_idea.assert_not_called()

    def test_normalize_truncates_title(self):
        adapter, _ = self._adapter()
        normalized = adapter.normalize(self._record(title="x" * 300))
        assert len(normalized.title) == 255

    def test_normalize_rejects_invalid(self):
        adapter, _ = self._adapter()
        with pytest.raises(ValueError):
            adapter.normalize(self._record(description=""))
