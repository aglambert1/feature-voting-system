"""Unit tests for count_gaps.

Counts gaps in a CompetitorFunctionalReport across the post-JTBD-redesign
data layout (where gaps live in functional_comparison/job_assessments) and
the legacy layout (where gaps lived in gaps_deep_dive). The function is
called at audit-task completion time and at API list time; both must agree.
"""

from app.services.competitive_report_metrics import count_gaps


def _comparison(*statuses):
    """Build a functional_comparison list of dicts with the given mapping_status values."""
    return [
        {"feature_category": "Cat", "competitor_feature_name": f"f{i}",
         "functional_description": "...", "mapping_status": status}
        for i, status in enumerate(statuses)
    ]


def _assessment(*positions):
    """Build a single job_assessment with features at the given positions."""
    return {
        "job_id": "j1",
        "features": [
            {"feature_name": f"f{i}", "whose": "theirs", "position": p}
            for i, p in enumerate(positions)
        ],
    }


class TestCountGapsFromFunctionalComparison:
    """Preferred source — populated in Stage 1 regardless of job map presence."""

    def test_counts_gap_entries(self):
        report = {
            "functional_comparison": _comparison("Gap", "Parity", "Gap", "Differentiator"),
        }
        assert count_gaps(report) == 2

    def test_zero_gaps_when_only_parity_or_differentiator(self):
        report = {
            "functional_comparison": _comparison("Parity", "Differentiator", "Advantage"),
        }
        assert count_gaps(report) == 0

    def test_does_not_fall_back_when_functional_comparison_present_with_zero_gaps(self):
        """Stage 1 ran successfully with zero gaps — that's a real answer.
        We must not fall through to gaps_deep_dive (which may contain stale data)."""
        report = {
            "functional_comparison": _comparison("Parity", "Advantage"),
            "gaps_deep_dive": [{"feature_name": "stale"}, {"feature_name": "stale2"}],
        }
        assert count_gaps(report) == 0


class TestCountGapsFromJobAssessments:
    """Fallback when functional_comparison is missing or empty."""

    def test_counts_position_gap_features(self):
        report = {
            "functional_comparison": [],
            "job_assessments": [
                _assessment("gap", "advantage", "gap"),
                _assessment("parity", "gap"),
            ],
        }
        assert count_gaps(report) == 3

    def test_handles_missing_features_array(self):
        report = {
            "functional_comparison": [],
            "job_assessments": [{"job_id": "j1"}],
        }
        assert count_gaps(report) == 0

    def test_skips_non_dict_features(self):
        report = {
            "functional_comparison": [],
            "job_assessments": [{"job_id": "j1", "features": ["bad", None, {"position": "gap"}]}],
        }
        assert count_gaps(report) == 1


class TestCountGapsFromGapsDeepDive:
    """Legacy fallback for no-job-map reports."""

    def test_counts_gaps_deep_dive_entries(self):
        report = {
            "functional_comparison": None,
            "job_assessments": None,
            "gaps_deep_dive": [
                {"feature_name": "X", "user_problem": "..."},
                {"feature_name": "Y", "user_problem": "..."},
                {"feature_name": "Z", "user_problem": "..."},
            ],
        }
        assert count_gaps(report) == 3


class TestCountGapsEdgeCases:

    def test_returns_zero_for_none(self):
        assert count_gaps(None) == 0

    def test_returns_zero_for_empty_report(self):
        assert count_gaps({}) == 0

    def test_returns_zero_when_all_fields_null(self):
        report = {"functional_comparison": None, "job_assessments": None, "gaps_deep_dive": None}
        assert count_gaps(report) == 0

    def test_works_with_orm_attribute_access(self):
        """Both API call site (passes ORM model) and task call site (passes dict)
        must work. Simulate ORM attribute access via a SimpleNamespace."""
        from types import SimpleNamespace
        report = SimpleNamespace(
            functional_comparison=_comparison("Gap", "Gap", "Parity"),
            job_assessments=None,
            gaps_deep_dive=None,
        )
        assert count_gaps(report) == 2
