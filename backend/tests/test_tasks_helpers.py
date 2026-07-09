"""Unit tests for pure helpers in app/queue/helpers.py.

These don't touch Celery or the DB — they cover the small functions used by
the triage and synthesis paths to keep their data hygiene predictable.
"""

import pytest

from app.queue.helpers import (
    _extract_competitor_names,
    _sanitize_existing_feature_info,
    _authoritative_job_key,
    _authoritative_competitor_names,
)


class TestAuthoritativeCompetitorNames:
    """`_authoritative_competitor_names` reads the deterministic competitor list
    a synthesis writer stamped into source_metadata, so triage preserves it
    instead of trusting the agent's (often anonymized) list. Returns None when
    there is no authoritative data, signalling the caller to fall back."""

    def test_returns_competitor_names_list(self):
        assert _authoritative_competitor_names(
            {"competitor_names": ["Acme", "Globex"]}
        ) == ["Acme", "Globex"]

    def test_falls_back_to_singular_competitor_name(self):
        assert _authoritative_competitor_names(
            {"competitor_name": "Acme"}
        ) == ["Acme"]

    def test_prefers_plural_over_singular(self):
        assert _authoritative_competitor_names(
            {"competitor_names": ["Acme"], "competitor_name": "Globex"}
        ) == ["Acme"]

    def test_returns_none_when_no_competitor_key(self):
        # No competitor key at all (e.g. customer-submitted idea) → fall back.
        assert _authoritative_competitor_names({"opportunity_id": 5}) is None

    def test_empty_list_is_authoritative_not_fallback(self):
        # A customer-only opportunity stamps competitor_names: [] — that empty
        # list is authoritative (show no competitors), NOT a signal to fall back
        # to the agent's possibly-hallucinated list.
        assert _authoritative_competitor_names({"competitor_names": []}) == []

    def test_returns_none_for_none_metadata(self):
        assert _authoritative_competitor_names(None) is None

    def test_returns_none_for_non_dict(self):
        assert _authoritative_competitor_names("not a dict") is None
        assert _authoritative_competitor_names(42) is None

    def test_returns_new_list_not_alias(self):
        src = ["Acme", "Globex"]
        out = _authoritative_competitor_names({"competitor_names": src})
        assert out == src and out is not src


class TestAuthoritativeJobKey:
    """`_authoritative_job_key` reads a deterministically-set job_id_key from an
    idea's source_metadata so triage preserves the synthesis-assigned job link
    instead of re-deriving it via embedding similarity."""

    def test_returns_key_when_present(self):
        assert _authoritative_job_key({"job_id_key": "j3"}) == "j3"

    def test_returns_none_when_key_missing(self):
        assert _authoritative_job_key({"opportunity_id": 5}) is None

    def test_returns_none_when_key_is_none(self):
        assert _authoritative_job_key({"job_id_key": None}) is None

    def test_returns_none_for_empty_string(self):
        assert _authoritative_job_key({"job_id_key": ""}) is None

    def test_returns_none_for_none_metadata(self):
        assert _authoritative_job_key(None) is None

    def test_returns_none_for_non_dict(self):
        assert _authoritative_job_key("not a dict") is None
        assert _authoritative_job_key(42) is None


class TestExtractCompetitorNames:
    """`_extract_competitor_names` reads the competitors list from a
    SynthesizedOpportunity.competitive_evidence blob. Used by both the auto-gen
    loop and the manual create-from-opportunity endpoint."""

    def test_returns_competitors_when_present(self):
        ce = {"competitors": ["Acme", "Globex"], "competitor_count": 2}
        assert _extract_competitor_names(ce) == ["Acme", "Globex"]

    def test_returns_empty_for_none(self):
        assert _extract_competitor_names(None) == []

    def test_returns_empty_for_dict_without_competitors_key(self):
        assert _extract_competitor_names({"prevalence": "Common"}) == []

    def test_returns_empty_when_competitors_is_null(self):
        assert _extract_competitor_names({"competitors": None}) == []

    def test_filters_out_falsy_entries(self):
        assert _extract_competitor_names({"competitors": ["Acme", None, "", "Globex"]}) == ["Acme", "Globex"]

    def test_returns_empty_for_non_dict(self):
        assert _extract_competitor_names("not a dict") == []
        assert _extract_competitor_names(["list", "passed"]) == []
        assert _extract_competitor_names(42) == []


class TestSanitizeExistingFeatureInfo:
    """`_sanitize_existing_feature_info` strips placeholder/non-URL values from
    `source_url` so the frontend never receives e.g. "N/A" (which would render
    as a relative URL like localhost:5173/N/A)."""

    def test_keeps_valid_https_url(self):
        info = {"feature_name": "X", "source_url": "https://example.com/docs"}
        result = _sanitize_existing_feature_info(info)
        assert result["source_url"] == "https://example.com/docs"

    def test_keeps_valid_http_url(self):
        info = {"feature_name": "X", "source_url": "http://example.com/docs"}
        assert _sanitize_existing_feature_info(info)["source_url"] == "http://example.com/docs"

    def test_strips_whitespace_around_url(self):
        info = {"feature_name": "X", "source_url": "  https://example.com  "}
        assert _sanitize_existing_feature_info(info)["source_url"] == "https://example.com"

    def test_nullifies_na_placeholder(self):
        info = {"feature_name": "X", "source_url": "N/A"}
        assert _sanitize_existing_feature_info(info)["source_url"] is None

    def test_nullifies_empty_string(self):
        info = {"feature_name": "X", "source_url": ""}
        assert _sanitize_existing_feature_info(info)["source_url"] is None

    def test_nullifies_relative_path(self):
        info = {"feature_name": "X", "source_url": "/docs/feature"}
        assert _sanitize_existing_feature_info(info)["source_url"] is None

    def test_nullifies_non_string_url(self):
        info = {"feature_name": "X", "source_url": 42}
        assert _sanitize_existing_feature_info(info)["source_url"] is None

    def test_preserves_null_url(self):
        info = {"feature_name": "X", "source_url": None}
        assert _sanitize_existing_feature_info(info)["source_url"] is None

    def test_preserves_other_fields(self):
        info = {
            "feature_name": "Receipt scanning",
            "feature_description": "Scan receipts via mobile camera",
            "similarity_score": 0.91,
            "source_url": "N/A",
        }
        result = _sanitize_existing_feature_info(info)
        assert result["feature_name"] == "Receipt scanning"
        assert result["feature_description"] == "Scan receipts via mobile camera"
        assert result["similarity_score"] == 0.91
        assert result["source_url"] is None

    def test_does_not_mutate_input(self):
        info = {"feature_name": "X", "source_url": "N/A"}
        _sanitize_existing_feature_info(info)
        # Original dict still has the bad URL — sanitizer returns a copy.
        assert info["source_url"] == "N/A"

    def test_passthrough_for_non_dict(self):
        assert _sanitize_existing_feature_info(None) is None
        assert _sanitize_existing_feature_info("string") == "string"


class TestFailJob:
    """`fail_job` is the shared best-effort failure marker used by all Celery
    task except-blocks. It must mark the job failed when possible and never
    raise — a status-update failure must not mask the original task error."""

    def test_marks_job_failed_with_traceback(self, db_session):
        from app.models.queue import JobType, JobStatus
        from app.queue.helpers import fail_job
        from app.services.queue_service import QueueService

        job = QueueService(db_session).create_job(
            job_type=JobType.PRODUCT_ANALYSIS, input_data={}
        )
        fail_job(db_session, job.id, "boom", "Traceback: ...", task_name="test_task")

        db_session.refresh(job)
        assert job.status == JobStatus.FAILURE
        assert job.error_message == "boom"
        assert job.error_traceback == "Traceback: ..."

    def test_none_db_is_noop(self):
        from app.queue.helpers import fail_job

        fail_job(None, 123, "boom")  # must not raise

    def test_swallows_status_update_failure(self, db_session):
        from app.queue.helpers import fail_job

        # Nonexistent job id → QueueService raises internally; fail_job swallows.
        fail_job(db_session, 999999, "boom", "tb")
