"""Unit tests for pure helpers in app/queue/tasks.py.

These don't touch Celery or the DB — they cover the small functions used by
the triage and synthesis paths to keep their data hygiene predictable.
"""

import pytest

from app.queue.tasks import _extract_competitor_names, _sanitize_existing_feature_info


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
