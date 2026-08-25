"""
Derived job-level position for competitive assessments.

Stage 2 of the functional audit scores our product and the competitor against
each job on a 1-10 scale. Those raw scores are too fine-grained to compare run
over run: a 7 in one run and an 8 in the next, for the same capability and the
same evidence, is within the model's own noise rather than a real change.

The Stage 2 prompt's rubric is five two-point bands (9-10 best-in-class, 7-8
strong, 5-6 adequate, 3-4 minimal, 1-2 barely). The model effectively picks a
band and then a point inside it — the band carries the signal, the point within
it does not. Quantizing a score back to its band therefore discards exactly the
jitter that isn't meaningful, and the thresholds are not invented here: they are
the bands the model was instructed to use.

Position is always DERIVED, never authored by the model, so it cannot disagree
with the scores it summarizes. It is the stable projection used for change
detection; the scores remain the analytical output a human reads.

`differentiator` is deliberately not derivable — distinguishing it from
`advantage` needs a judgement the scores don't carry. It stays a feature-level
value only (see `JobFeatureAssessment.position`).
"""

from typing import Any, Dict, List, Optional

POSITION_ADVANTAGE = "advantage"
POSITION_GAP = "gap"
POSITION_PARITY = "parity"
POSITION_UNKNOWN = "unknown"


def normalize_statement(statement: Any) -> str:
    """Normalize a job statement for comparison across report versions.

    A job key (`j1`) is stable, but the statement it points at is editable. Two
    versions of a report can therefore carry the same key for materially
    different jobs. Comparison collapses whitespace and case so that a typo fix
    or reflow isn't mistaken for a restatement, while any real edit to the
    wording is caught.

    Deliberately an exact comparison after normalizing rather than a similarity
    score: the result drives whether a verdict is comparable at all, and that
    decision should be deterministic and explainable rather than sitting on a
    threshold.
    """
    if not isinstance(statement, str):
        return ""
    return " ".join(statement.split()).casefold()

# A score of 0 means "unknown", not "worst possible" — see JobAssessment.
_UNKNOWN_SCORE = 0
_MAX_SCORE = 10


def score_to_tier(score: Any) -> Optional[int]:
    """Map a 1-10 rubric score to its band (1-5).

    Returns None when the score is 0 (explicitly "unknown"), missing, or
    outside the valid range — callers must not treat that as a low score.
    """
    if isinstance(score, bool):  # bool is an int subclass; reject it explicitly
        return None
    try:
        value = int(score)
    except (TypeError, ValueError):
        return None
    if value <= _UNKNOWN_SCORE or value > _MAX_SCORE:
        return None
    return (value + 1) // 2


def derive_system_position(our_score: Any, competitor_score: Any) -> str:
    """Compare two rubric scores by band and return the derived position.

    A higher competitor band is a gap for us; a higher band of ours is an
    advantage; the same band is parity. If either score is unknown the
    comparison is unknown — never parity, which would assert equivalence we
    have no basis for.
    """
    our_tier = score_to_tier(our_score)
    their_tier = score_to_tier(competitor_score)

    if our_tier is None or their_tier is None:
        return POSITION_UNKNOWN
    if their_tier > our_tier:
        return POSITION_GAP
    if their_tier < our_tier:
        return POSITION_ADVANTAGE
    return POSITION_PARITY


def evidence_ids_for_assessment(assessment: Dict[str, Any]) -> set:
    """Collect every evidence id cited by an assessment's features.

    Used by change detection to tell a position flip backed by new evidence
    from one that moved on its own.
    """
    ids = set()
    for feature in (assessment.get("features") or []):
        if not isinstance(feature, dict):
            continue
        for eid in (feature.get("evidence_ids") or []):
            if eid is not None:
                ids.add(eid)
    return ids


def enrich_assessments(
    assessments: Optional[List[Dict[str, Any]]],
    previous_assessments: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Add the derived system_position and carry forward human review state.

    The system position is recomputed on every run. Human review state
    (human_position, reviewed_at, reviewed_by) is carried forward from the
    previous report version so a re-audit never silently discards a PM's
    override — the system verdict is regenerated alongside it, not on top of it.

    Review is optional: an assessment nobody has looked at keeps human_position
    as None, which is a normal state and not a deficiency.

    A review is made against a job as it was worded at the time. Because job
    keys are stable but statements are editable, an override can outlive the
    statement that justified it. When that happens the override is kept but
    marked `review_stale`, rather than silently dropped (destroying a PM's work
    without asking) or silently kept (presenting a judgement about one job as
    though it were about another). Staleness sticks until someone reviews again.
    """
    if not assessments:
        return []

    prior_by_job = {
        a.get("job_id"): a
        for a in (previous_assessments or [])
        if isinstance(a, dict) and a.get("job_id")
    }

    enriched = []
    for assessment in assessments:
        if not isinstance(assessment, dict):
            continue
        item = dict(assessment)
        item["system_position"] = derive_system_position(
            item.get("our_score"), item.get("competitor_score")
        )

        prior = prior_by_job.get(item.get("job_id")) or {}
        item["human_position"] = prior.get("human_position")
        item["reviewed_at"] = prior.get("reviewed_at")
        item["reviewed_by"] = prior.get("reviewed_by")
        item["reviewed_job_statement"] = prior.get("reviewed_job_statement")

        # The wording the review was actually made against. Falls back to the
        # previous run's statement for reviews recorded before that snapshot was
        # kept — weaker, but it still catches a restatement at the run where it
        # happens, and the sticky flag carries the finding forward from there.
        review_basis = (
            item.get("reviewed_job_statement")
            or prior.get("job_statement")
        )

        already_stale = bool(prior.get("review_stale"))
        drifted = bool(
            item.get("human_position")
            and review_basis
            and normalize_statement(review_basis)
            != normalize_statement(item.get("job_statement"))
        )
        item["review_stale"] = bool(item.get("human_position")) and (
            already_stale or drifted
        )

        enriched.append(item)

    return enriched
