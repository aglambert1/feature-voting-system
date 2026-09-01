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

        enriched = enrich_assessments(
            fresh_from_agent, previous, self_scores={"j1": 4}, self_assessment_version=2
        )

        assert enriched[0]["human_position"] == "parity"
        assert enriched[0]["reviewed_by"] == 3
        # The system verdict is regenerated alongside the human's, not on top.
        assert enriched[0]["system_position"] == "gap"

    def test_unreviewed_assessments_stay_unreviewed(self):
        # Review is optional — a PM may accept system levels without looking.
        enriched = enrich_assessments(
            [{"job_id": "j1", "competitor_score": 5, "features": []}],
            previous_assessments=None,
            self_scores={"j1": 5},
        )

        assert enriched[0]["human_position"] is None
        assert enriched[0]["reviewed_at"] is None
        assert enriched[0]["system_position"] == "parity"

    def test_override_does_not_register_as_a_competitor_change(self):
        # A human disagreeing with the model is not the market moving.
        previous = _report([_assessment("j1", 5, 7, human_position=None)])
        current = _report([_assessment("j1", 5, 7, human_position="advantage")])

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)

        assert diff["job_position_changes"] == []


# ---------------------------------------------------------------------------
# Restated jobs — the same key can describe a different job
# ---------------------------------------------------------------------------

class TestRestatedJobs:
    def test_restated_job_is_not_reported_as_a_position_change(self):
        # j1 means something different now, so its old and new positions are
        # not two readings of the same thing.
        previous = _report([_assessment("j1", 7, 7)])
        current = _report([_assessment("j1", 3, 9, job_statement="An entirely different job")])

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)

        assert diff["job_position_changes"] == []
        assert len(diff["jobs_restated"]) == 1
        restated = diff["jobs_restated"][0]
        assert restated["job_id"] == "j1"
        assert restated["old_job_statement"] == "Statement for j1"
        assert restated["new_job_statement"] == "An entirely different job"
        assert restated["positions_comparable"] is False
        assert "not comparable" in diff["summary"]

    @pytest.mark.parametrize("variant", [
        "  Statement for j1  ",
        "Statement  for   j1",
        "STATEMENT FOR J1",
        "Statement for j1\n",
    ])
    def test_whitespace_and_case_changes_are_not_restatements(self, variant):
        previous = _report([_assessment("j1", 5, 7)])
        current = _report([_assessment("j1", 5, 7, job_statement=variant)])

        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)

        assert diff["jobs_restated"] == []
        assert diff["job_position_changes"] == []


class TestOverrideStaleness:
    def test_override_goes_stale_when_the_job_is_restated(self):
        previous = [_assessment(
            "j1", 5, 7,
            human_position="parity",
            reviewed_at="2026-08-01T00:00:00Z",
            reviewed_by=3,
            reviewed_job_statement="Statement for j1",
        )]
        fresh = [{
            "job_id": "j1",
            "job_statement": "A materially rewritten job",
            "our_score": 5,
            "competitor_score": 7,
            "features": [],
        }]

        enriched = enrich_assessments(fresh, previous)

        # Kept, not silently dropped — but flagged rather than silently trusted.
        assert enriched[0]["human_position"] == "parity"
        assert enriched[0]["review_stale"] is True

    def test_override_stays_fresh_when_the_job_is_unchanged(self):
        previous = [_assessment(
            "j1", 5, 7,
            human_position="parity",
            reviewed_job_statement="Statement for j1",
        )]
        fresh = [{
            "job_id": "j1",
            "job_statement": "Statement for j1",
            "our_score": 4,
            "competitor_score": 9,
            "features": [],
        }]

        enriched = enrich_assessments(fresh, previous)

        assert enriched[0]["review_stale"] is False

    def test_staleness_is_sticky_across_later_runs(self):
        # Once the basis is gone it stays gone until someone reviews again,
        # even though later runs no longer see the original wording.
        stale = [_assessment(
            "j1", 5, 7,
            job_statement="A materially rewritten job",
            human_position="parity",
            reviewed_job_statement="Statement for j1",
            review_stale=True,
        )]
        fresh = [{
            "job_id": "j1",
            "job_statement": "A materially rewritten job",
            "our_score": 5,
            "competitor_score": 7,
            "features": [],
        }]

        enriched = enrich_assessments(fresh, stale)

        assert enriched[0]["review_stale"] is True

    def test_unreviewed_assessment_is_never_stale(self):
        previous = [_assessment("j1", 5, 7)]
        fresh = [{
            "job_id": "j1",
            "job_statement": "A materially rewritten job",
            "our_score": 5,
            "competitor_score": 7,
            "features": [],
        }]

        enriched = enrich_assessments(fresh, previous)

        assert enriched[0]["human_position"] is None
        assert enriched[0]["review_stale"] is False

    def test_restatement_detected_without_a_recorded_review_basis(self):
        # Reviews recorded before reviewed_job_statement existed fall back to
        # the previous run's wording.
        previous = [_assessment("j1", 5, 7, human_position="parity")]
        fresh = [{
            "job_id": "j1",
            "job_statement": "A materially rewritten job",
            "our_score": 5,
            "competitor_score": 7,
            "features": [],
        }]

        enriched = enrich_assessments(fresh, previous)

        assert enriched[0]["review_stale"] is True



# ---------------------------------------------------------------------------
# Our score is joined, not authored by the audit
# ---------------------------------------------------------------------------

class TestOurScoreIsJoined:
    def test_audit_supplied_our_score_is_discarded(self):
        # An audit has no standing to score us. Letting one through would reintroduce
        # the per-competitor divergence the self-assessment exists to remove.
        enriched = enrich_assessments(
            [{"job_id": "j1", "competitor_score": 8, "our_score": 10}],
            self_scores={"j1": 3},
        )
        assert enriched[0]["our_score"] == 3
        assert enriched[0]["system_position"] == "gap"

    def test_position_is_unknown_without_a_self_assessment(self):
        # Position needs both sides. Guessing one would assert a comparison we cannot make.
        enriched = enrich_assessments([{"job_id": "j1", "competitor_score": 8}])
        assert enriched[0]["system_position"] == "unknown"
        assert enriched[0]["our_score"] is None

    def test_records_which_self_assessment_was_used(self):
        enriched = enrich_assessments(
            [{"job_id": "j1", "competitor_score": 8}],
            self_scores={"j1": 4},
            self_assessment_version=7,
        )
        assert enriched[0]["self_assessment_version"] == 7

    def test_jobs_missing_from_the_self_assessment_are_unknown(self):
        enriched = enrich_assessments(
            [{"job_id": "j1", "competitor_score": 8}, {"job_id": "j2", "competitor_score": 5}],
            self_scores={"j1": 4},
        )
        by_job = {a["job_id"]: a for a in enriched}
        assert by_job["j1"]["system_position"] == "gap"
        assert by_job["j2"]["system_position"] == "unknown"


class TestFlipAttribution:
    """A flip can be caused by them, by us, or by both — and they mean different things."""

    def _pair(self, prev_ours, prev_theirs, curr_ours, curr_theirs):
        previous = _report([_assessment("j1", prev_ours, prev_theirs)])
        current = _report([_assessment("j1", curr_ours, curr_theirs)])
        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)
        return diff

    def test_competitor_moved(self):
        diff = self._pair(5, 5, 5, 9)
        assert diff["job_position_changes"][0]["attributed_to"] == "competitor"

    def test_we_moved(self):
        # We shipped something. Reporting this as competitor movement would be
        # actively misleading — nothing changed on their side.
        diff = self._pair(3, 7, 9, 7)
        change = diff["job_position_changes"][0]
        assert change["attributed_to"] == "us"
        assert "our side, not theirs" in diff["summary"]

    def test_both_moved(self):
        diff = self._pair(3, 9, 9, 3)
        assert diff["job_position_changes"][0]["attributed_to"] == "both"

    def test_score_known_becoming_unknown_is_unclear(self):
        # No band moved, yet position did — the inputs changed shape, not value.
        previous = _report([_assessment("j1", 5, 9)])
        current = _report([_assessment("j1", 0, 9)])
        diff = ChangeDetectionService.compute_functional_report_diff(current, previous)
        assert diff["job_position_changes"][0]["attributed_to"] == "unclear"
