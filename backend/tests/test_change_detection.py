"""
Tests for job-keyed change detection and derived job positions.

The behaviour under test exists because of a measured failure: two competitor
audits run on the same subject, with the same input, on the same day produced
different feature names for the same capability and disagreed on several job
verdicts. A diff keyed on feature names reported rewording as change; a diff on
raw 1-10 scores would report within-band jitter as change. These tests pin the
properties that make the diff trustworthy rather than merely present.
"""

import pytest

from app.services.change_detection_service import ChangeDetectionService
from app.utils.job_position import (
    derive_system_position,
    enrich_assessments,
    score_to_tier,
)


def _assessment(job_id, our, theirs, features=None, **extra):
    """Build an enriched assessment the way the task persists it."""
    base = {
        "job_id": job_id,
        "job_statement": f"Statement for {job_id}",
        "importance": "high",
        "our_score": our,
        "competitor_score": theirs,
        "score_rationale": "because",
        "features": features or [],
        "system_position": derive_system_position(our, theirs),
    }
    base.update(extra)
    return base


def _report(assessments, positioning="Unchanged positioning"):
    return {
        "job_assessments": assessments,
        "competitor_context": {"positioning": positioning},
    }


# ---------------------------------------------------------------------------
# Derived position
# ---------------------------------------------------------------------------

class TestScoreToTier:
    @pytest.mark.parametrize("score,tier", [
        (1, 1), (2, 1),
        (3, 2), (4, 2),
        (5, 3), (6, 3),
        (7, 4), (8, 4),
        (9, 5), (10, 5),
    ])
    def test_maps_score_to_rubric_band(self, score, tier):
        assert score_to_tier(score) == tier

    def test_zero_is_unknown_not_lowest(self):
        # 0 means "unknown" in JobAssessment, not "barely addresses the job".
        assert score_to_tier(0) is None

    @pytest.mark.parametrize("bad", [None, "", "high", -1, 11, True, False])
    def test_invalid_scores_are_unknown(self, bad):
        assert score_to_tier(bad) is None


class TestDeriveSystemPosition:
    def test_higher_competitor_band_is_a_gap(self):
        assert derive_system_position(5, 8) == "gap"

    def test_higher_our_band_is_an_advantage(self):
        assert derive_system_position(9, 4) == "advantage"

    def test_same_band_is_parity(self):
        assert derive_system_position(7, 8) == "parity"

    def test_within_band_jitter_does_not_change_position(self):
        # The whole point of banding: 7 vs 8 for the same capability is noise.
        assert derive_system_position(5, 7) == derive_system_position(6, 8)

    def test_unknown_score_never_reads_as_parity(self):
        # Asserting equivalence from a missing score would be a false claim.
        assert derive_system_position(0, 0) == "unknown"
        assert derive_system_position(7, 0) == "unknown"
        assert derive_system_position(0, 7) == "unknown"


# ---------------------------------------------------------------------------
# The core property: prose churn is not change
# ---------------------------------------------------------------------------

class TestRewordingIsNotChange:
    def test_renamed_feature_with_same_scores_reports_nothing(self):
        previous = _report([
            _assessment("j1", 5, 7, features=[{"feature_name": "Scheduled spend reports"}])
        ])
        current = _report([
            _assessment("j1", 5, 7, features=[{"feature_name": "Recurring report delivery"}])
        ])

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)

        assert diff["job_position_changes"] == []
        assert diff["summary"] == "No significant changes"

    def test_rationale_rewrite_reports_nothing(self):
        previous = _report([_assessment("j1", 5, 7, score_rationale="One phrasing")])
        current = _report([_assessment("j1", 5, 7, score_rationale="A totally different phrasing")])

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)

        assert diff["job_position_changes"] == []

    def test_score_jitter_inside_a_band_reports_nothing(self):
        previous = _report([_assessment("j1", 5, 7)])
        current = _report([_assessment("j1", 6, 8)])

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)

        assert diff["job_position_changes"] == []


# ---------------------------------------------------------------------------
# Real changes are detected
# ---------------------------------------------------------------------------

class TestRealChangesAreDetected:
    def test_position_flip_is_reported_with_both_positions(self):
        previous = _report([_assessment("j1", 7, 7)])   # parity
        current = _report([_assessment("j1", 5, 9)])    # gap

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)

        assert len(diff["job_position_changes"]) == 1
        change = diff["job_position_changes"][0]
        assert change["job_id"] == "j1"
        assert change["old_position"] == "parity"
        assert change["new_position"] == "gap"
        assert change["old_scores"] == {"ours": 7, "theirs": 7}
        assert change["new_scores"] == {"ours": 5, "theirs": 9}

    def test_newly_assessed_job_is_reported(self):
        previous = _report([_assessment("j1", 5, 5)])
        current = _report([_assessment("j1", 5, 5), _assessment("j2", 3, 9)])

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)

        assert [j["job_id"] for j in diff["jobs_added"]] == ["j2"]
        assert diff["jobs_added"][0]["position"] == "gap"

    def test_dropped_job_is_reported_with_prior_position(self):
        previous = _report([_assessment("j1", 5, 5), _assessment("j2", 3, 9)])
        current = _report([_assessment("j1", 5, 5)])

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)

        assert [j["job_id"] for j in diff["jobs_removed"]] == ["j2"]
        assert diff["jobs_removed"][0]["was_position"] == "gap"

    def test_positioning_change_is_reported(self):
        previous = _report([_assessment("j1", 5, 5)], positioning="Old story")
        current = _report([_assessment("j1", 5, 5)], positioning="New story")

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)

        assert diff["positioning_changes"] == {"old": "Old story", "new": "New story"}


# ---------------------------------------------------------------------------
# The instrumentation signal
# ---------------------------------------------------------------------------

class TestEvidenceBackedFlips:
    def test_flip_with_new_evidence_is_marked_substantiated(self):
        previous = _report([
            _assessment("j1", 7, 7, features=[{"feature_name": "A", "evidence_ids": [1]}])
        ])
        current = _report([
            _assessment("j1", 4, 9, features=[{"feature_name": "A", "evidence_ids": [1, 2]}])
        ])

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)
        change = diff["job_position_changes"][0]

        assert change["evidence_changed"] is True
        assert change["new_evidence_ids"] == [2]
        assert "with new evidence" in diff["summary"]

    def test_flip_without_new_evidence_is_marked_unsubstantiated(self):
        previous = _report([
            _assessment("j1", 7, 7, features=[{"feature_name": "A", "evidence_ids": [1]}])
        ])
        current = _report([
            _assessment("j1", 4, 9, features=[{"feature_name": "A", "evidence_ids": [1]}])
        ])

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)
        change = diff["job_position_changes"][0]

        assert change["evidence_changed"] is False
        assert change["new_evidence_ids"] == []
        assert "without new evidence" in diff["summary"]


# ---------------------------------------------------------------------------
# Degradation and human state
# ---------------------------------------------------------------------------

class TestNoJobAssessments:
    def test_missing_assessments_degrade_explicitly_rather_than_falling_back(self):
        # The old feature-name diff is deliberately not used as a fallback:
        # a known-noisy answer is worse than an explicit absence.
        previous = {"job_assessments": [], "competitor_context": {"positioning": "Same"}}
        current = {"job_assessments": [], "competitor_context": {"positioning": "Same"}}

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)

        assert diff["assessment_diff_available"] is False
        assert diff["job_position_changes"] == []
        assert diff["summary"] == "No job assessments to compare"

    def test_positioning_still_compared_without_assessments(self):
        previous = {"job_assessments": [], "competitor_context": {"positioning": "Old"}}
        current = {"job_assessments": [], "competitor_context": {"positioning": "New"}}

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)

        assert diff["assessment_diff_available"] is False
        assert diff["positioning_changes"] == {"old": "Old", "new": "New"}


class TestHumanVerdictsSurviveReaudit:
    def test_override_is_carried_forward(self):
        previous = [_assessment(
            "j1", 5, 7,
            human_position="parity",
            reviewed_at="2026-08-01T00:00:00Z",
            reviewed_by=3,
        )]
        fresh_from_agent = [{
            "job_id": "j1",
            "job_statement": "Statement for j1",
            "our_score": 4,
            "competitor_score": 9,
            "score_rationale": "new run",
            "features": [],
        }]

        enriched = enrich_assessments(fresh_from_agent, previous)

        assert enriched[0]["human_position"] == "parity"
        assert enriched[0]["reviewed_by"] == 3
        # The system verdict is regenerated alongside the human's, not on top.
        assert enriched[0]["system_position"] == "gap"

    def test_unreviewed_assessments_stay_unreviewed(self):
        # Review is optional — a PM may accept system levels without looking.
        enriched = enrich_assessments([
            {"job_id": "j1", "our_score": 5, "competitor_score": 5, "features": []}
        ], previous_assessments=None)

        assert enriched[0]["human_position"] is None
        assert enriched[0]["reviewed_at"] is None
        assert enriched[0]["system_position"] == "parity"

    def test_override_does_not_register_as_a_competitor_change(self):
        # A human disagreeing with the model is not the market moving.
        previous = _report([_assessment("j1", 5, 7, human_position=None)])
        current = _report([_assessment("j1", 5, 7, human_position="advantage")])

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)

        assert diff["job_position_changes"] == []
