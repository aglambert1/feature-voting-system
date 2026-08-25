"""
Change Detection Service.

Computes structured diffs when competitive reports are re-run,
surfacing what actually changed between versions.

The diff is keyed on `job_id`, never on feature names. Feature names are
model-generated prose and vary between runs describing the same capability
("Scheduled spend reports" vs "Recurring report delivery"), so a name-keyed
diff reports a removal plus an addition when nothing has changed. The stable
coordinate is (job, competitor), and the comparable value on it is the derived
`system_position` — a band comparison rather than a raw score, so within-band
score jitter doesn't register as change. See `app.utils.job_position`.

A position flip is a CANDIDATE change, not a confirmed one: two runs on the
same subject with the same evidence can disagree. Each flip is therefore
tagged with whether the underlying evidence changed, so a caller can weigh a
flip backed by new sources differently from one that moved on its own. What to
do with an unsubstantiated flip — suppress it, downgrade it, escalate it — is
the caller's decision, not this service's.

Job keys are stable but the statements behind them are editable, so the same
key can describe materially different jobs in two versions. Those are reported
as restatements rather than position changes: comparing verdicts across a
rewritten job is the feature-name error one level up.

Human overrides (`human_position`) are deliberately ignored here. A PM
disagreeing with the model is not a competitor changing, and folding overrides
into the diff would report a correction as market movement.
"""

from typing import Dict, Any, List, Optional

from app.utils.job_position import evidence_ids_for_assessment, normalize_statement


class ChangeDetectionService:
    """Computes structured diffs between report versions."""

    @staticmethod
    def compute_functional_report_diff(
        current_data: Dict[str, Any],
        previous_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare two functional audit report versions.

        Args:
            current_data: Dict with job_assessments and competitor_context
                          from the new report
            previous_data: Same structure from the previous report version

        Returns:
            Structured diff with job_position_changes, jobs_added,
            jobs_removed, positioning_changes, assessment_diff_available,
            and summary.
        """
        curr_assessments = {
            a.get("job_id"): a
            for a in (current_data.get("job_assessments") or [])
            if isinstance(a, dict) and a.get("job_id")
        }
        prev_assessments = {
            a.get("job_id"): a
            for a in (previous_data.get("job_assessments") or [])
            if isinstance(a, dict) and a.get("job_id")
        }

        # Positioning is comparable regardless of whether a job map exists.
        positioning_changes = None
        curr_context = current_data.get("competitor_context") or {}
        prev_context = previous_data.get("competitor_context") or {}
        if curr_context and prev_context:
            old_pos = prev_context.get("positioning", "")
            new_pos = curr_context.get("positioning", "")
            if old_pos != new_pos and old_pos and new_pos:
                positioning_changes = {"old": old_pos, "new": new_pos}

        # Without job assessments on both sides there is no stable coordinate
        # to compare. The old feature-name diff is not used as a fallback: it
        # reports rewording as change, and a known-noisy result is worse than
        # an explicit absence.
        if not curr_assessments or not prev_assessments:
            return {
                "job_position_changes": [],
                "jobs_added": [],
                "jobs_removed": [],
                "jobs_restated": [],
                "positioning_changes": positioning_changes,
                "assessment_diff_available": False,
                "summary": ChangeDetectionService._build_functional_summary(
                    [], [], [], positioning_changes, assessment_diff_available=False
                ),
            }

        curr_ids = set(curr_assessments.keys())
        prev_ids = set(prev_assessments.keys())

        jobs_added = [
            {
                "job_id": job_id,
                "job_statement": curr_assessments[job_id].get("job_statement", ""),
                "position": curr_assessments[job_id].get("system_position"),
            }
            for job_id in sorted(curr_ids - prev_ids)
        ]

        jobs_removed = [
            {
                "job_id": job_id,
                "job_statement": prev_assessments[job_id].get("job_statement", ""),
                "was_position": prev_assessments[job_id].get("system_position"),
            }
            for job_id in sorted(prev_ids - curr_ids)
        ]

        job_position_changes = []
        jobs_restated = []
        for job_id in sorted(curr_ids & prev_ids):
            curr = curr_assessments[job_id]
            prev = prev_assessments[job_id]

            old_position = prev.get("system_position")
            new_position = curr.get("system_position")

            # Job keys are stable but their statements are editable. If the
            # statement changed, the two versions of this key describe
            # materially different jobs and their positions are not comparable —
            # the same error as diffing on feature names, one level up. Report
            # the restatement instead of a change that cannot be interpreted.
            if normalize_statement(prev.get("job_statement")) != normalize_statement(
                curr.get("job_statement")
            ):
                jobs_restated.append({
                    "job_id": job_id,
                    "old_job_statement": prev.get("job_statement", ""),
                    "new_job_statement": curr.get("job_statement", ""),
                    "old_position": old_position,
                    "new_position": new_position,
                    "positions_comparable": False,
                })
                continue

            if old_position == new_position:
                continue

            prev_evidence = evidence_ids_for_assessment(prev)
            curr_evidence = evidence_ids_for_assessment(curr)
            new_evidence = curr_evidence - prev_evidence

            job_position_changes.append({
                "job_id": job_id,
                "job_statement": curr.get("job_statement", ""),
                "importance": curr.get("importance", ""),
                "old_position": old_position,
                "new_position": new_position,
                "old_scores": {
                    "ours": prev.get("our_score"),
                    "theirs": prev.get("competitor_score"),
                },
                "new_scores": {
                    "ours": curr.get("our_score"),
                    "theirs": curr.get("competitor_score"),
                },
                "confidence": curr.get("confidence"),
                # The instrumentation signal: a flip with no new evidence
                # behind it is more likely model variance than market change.
                "evidence_changed": bool(new_evidence),
                "new_evidence_ids": sorted(new_evidence),
            })

        summary = ChangeDetectionService._build_functional_summary(
            job_position_changes, jobs_added, jobs_removed, positioning_changes,
            jobs_restated=jobs_restated,
        )

        return {
            "job_position_changes": job_position_changes,
            "jobs_added": jobs_added,
            "jobs_removed": jobs_removed,
            "jobs_restated": jobs_restated,
            "positioning_changes": positioning_changes,
            "assessment_diff_available": True,
            "summary": summary,
        }

    @staticmethod
    def _build_functional_summary(
        job_position_changes: List,
        jobs_added: List,
        jobs_removed: List,
        positioning_changes: Optional[Dict],
        assessment_diff_available: bool = True,
        jobs_restated: Optional[List] = None,
    ) -> str:
        """Generate human-readable summary for functional report diff.

        Flips backed by new evidence are reported separately from flips that
        moved without any: the second group is the one a reader should treat
        with suspicion rather than act on.
        """
        parts = []

        if job_position_changes:
            substantiated = sum(
                1 for c in job_position_changes if c.get("evidence_changed")
            )
            unsubstantiated = len(job_position_changes) - substantiated
            if substantiated:
                parts.append(f"{substantiated} job position change(s) with new evidence")
            if unsubstantiated:
                parts.append(
                    f"{unsubstantiated} job position change(s) without new evidence"
                )
        if jobs_added:
            parts.append(f"{len(jobs_added)} job(s) newly assessed")
        if jobs_removed:
            parts.append(f"{len(jobs_removed)} job(s) no longer assessed")
        if jobs_restated:
            parts.append(
                f"{len(jobs_restated)} job(s) restated — positions not comparable"
            )
        if positioning_changes:
            parts.append("positioning changed")

        if not parts:
            if not assessment_diff_available:
                return "No job assessments to compare"
            return "No significant changes"

        if not assessment_diff_available:
            parts.append("job assessments unavailable for comparison")

        return ", ".join(parts)
