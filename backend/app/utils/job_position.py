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


def verdict_grounding(
    our_confidence: Optional[str],
    corroboration_total: int = 0,
    human_position: Optional[str] = None,
) -> tuple:
    """Whether a comparison verdict is worth stating, and why not when it isn't.

    Returns (grounded: bool, reason: Optional[str]).

    A verdict is a claim about how we compare, and it is only as good as our own score.
    The job map is usually generated from the product's own description, so a self-score
    with low confidence and nothing external corroborating it is close to a restatement
    of marketing copy — and rendering it as a confident `GAP` or `ADVANTAGE` is worse
    than saying nothing, because a reader cannot tell the difference.

    Withheld deliberately per job rather than per report. The weakness is not uniform:
    some jobs carry customer signal and deserve a verdict, others do not, and a
    report-wide switch would discard the earned verdicts along with the unearned. It also
    means verdicts appear one by one as the map earns them, with no threshold to cross.

    Suppression applies ONLY to the comparison. The competitor's own score is researched
    independently of our map and is reported at full strength either way.

    Note the asymmetry: an override grounds the VERDICT, not our score. The PM judged the
    comparison, not our capability — so our score stays withheld while the verdict shows.
    """
    # A PM's override IS the missing grounding, not an exception to it. The reason a
    # verdict is withheld is that our score rests on the product description the job map
    # was derived from — circular. Someone saying "this is a differentiator" applies
    # knowledge that is not in that description, which breaks the circle. Treating their
    # judgement as ungrounded would be exactly backwards.
    if human_position:
        return True, None
    if corroboration_total > 0:
        return True, None
    if (our_confidence or "").lower() != "low":
        return True, None
    return False, (
        "Our score for this job rests only on the product description — the "
        "self-assessment rated its own confidence low, and no customer signal, "
        "lost deal, or evidence record has linked to it."
    )


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
    self_scores: Optional[Dict[str, int]] = None,
    self_assessment_version: Optional[int] = None,
    self_confidences: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Join our score in, derive system_position, and carry forward human review state.

    An audit scores the competitor only. Our score comes from the product's own
    self-assessment, joined here by job_id — so it is one number per job rather than a
    different one in every competitor's report. `our_score` is still written onto the
    stored assessment, but as a joined value rather than something the agent authored;
    `self_assessment_version` records which assessment it came from.

    Position needs both sides, so a job with no self-assessment score is `unknown`
    rather than guessed. Audits still produce competitor scores without one — the
    comparison simply cannot be stated until our side is assessed.

    Our confidence is joined alongside our score. It is not decoration: a verdict built
    on a self-score with nothing behind it looks exactly as authoritative as one built on
    evidence, and presenting the two identically is how a circular map produces confident
    nonsense. See `verdict_grounding`.

    The system position is recomputed on every run. Human review state
    (human_position, reviewed_at, reviewed_by) is carried forward from the
    previous report version so a re-audit never silently discards a PM's
    override — the system verdict is regenerated alongside it, not on top of it.

    Review is optional: an assessment nobody has looked at keeps human_position
    as None, which is a normal state and not a deficiency.

    A review is made against a job as it was worded at the time. Because job
    keys are stable but statements are editable, a review can outlive the
    statement that justified it. When that happens it is kept but marked
    `review_stale`, rather than silently dropped (destroying a PM's work
    without asking) or silently kept (presenting a judgement about one job as
    though it were about another). Staleness sticks until someone reviews again.

    This applies to a plain confirmation as much as to an override: agreeing
    with a verdict is still a judgement about the job as it was worded, and a
    restatement invalidates it just the same.
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

        # Our score is joined from the self-assessment, not taken from the audit. If the
        # agent emitted one anyway it is discarded: an audit has no standing to score us,
        # and letting it through would reintroduce the per-competitor divergence this
        # exists to remove.
        our_score = (self_scores or {}).get(item.get("job_id"))
        item["our_score"] = our_score
        item["our_confidence"] = (self_confidences or {}).get(item.get("job_id"))
        item["self_assessment_version"] = self_assessment_version

        item["system_position"] = derive_system_position(
            our_score, item.get("competitor_score")
        )

        prior = prior_by_job.get(item.get("job_id")) or {}
        item["human_position"] = prior.get("human_position")
        item["reviewed_at"] = prior.get("reviewed_at")
        item["reviewed_by"] = prior.get("reviewed_by")
        item["reviewed_job_statement"] = prior.get("reviewed_job_statement")
        # The reason a PM gave is the most informative part of a review — "why did you
        # override this" is the question the record exists to answer. Dropping it on the
        # next audit would keep the verdict and lose its justification.
        item["review_note"] = prior.get("review_note")

        # The wording the review was actually made against. Falls back to the
        # previous run's statement for reviews recorded before that snapshot was
        # kept — weaker, but it still catches a restatement at the run where it
        # happens, and the sticky flag carries the finding forward from there.
        review_basis = (
            item.get("reviewed_job_statement")
            or prior.get("job_statement")
        )

        # Staleness attaches to any review, not just an override. Agreeing with a
        # verdict is still a judgement about the job as it was worded at the time, so a
        # restatement invalidates a confirmation exactly as much as a correction.
        reviewed = bool(item.get("reviewed_at"))
        already_stale = bool(prior.get("review_stale"))
        drifted = bool(
            reviewed
            and review_basis
            and normalize_statement(review_basis)
            != normalize_statement(item.get("job_statement"))
        )
        item["review_stale"] = reviewed and (already_stale or drifted)

        enriched.append(item)

    return enriched
