"""
Job coverage API — how well our product and each tracked competitor serve each job.

Two surfaces, both deliberately free of any LLM call:

- Self-assessment: trigger and read our own score per job.
- Job coverage: our score beside every tracked competitor's, one row per job.

The coverage view is a join over audits that have already run. It is not gated behind
synthesis, which is a different question — synthesis weighs all evidence and recommends
where to invest, while this reports what the audits found. A PM who has audited three
competitors can compare them immediately.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import verify_product_access as _verify_product_access
from app.models.competitive_reports import (
    CompetitorFunctionalReport,
    ProductSelfAssessment,
)
from app.models.competitor_intelligence import (
    CIProduct,
    ProductCompetitor,
    ProductJob,
    ProductPermissionLevel,
)
from app.models.queue import JobType as QueueJobType
from app.models.user import User
from app.services.job_provenance import map_health, signal_counts
from app.services.queue_service import QueueService
from app.utils.celery_utils import send_celery_task as send_task
from app.utils.job_position import verdict_grounding
from app.utils.security import get_current_active_user

router = APIRouter(
    prefix="/product-intelligence/products",
    tags=["Job Coverage"],
)


def _latest_self_assessment(db: Session, product_id: int) -> Optional[ProductSelfAssessment]:
    return (
        db.query(ProductSelfAssessment)
        .filter(ProductSelfAssessment.product_id == product_id)
        .order_by(ProductSelfAssessment.assessment_version.desc())
        .first()
    )


@router.post("/{product_id}/self-assessment")
def run_self_assessment(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Queue a self-assessment of our product against its job map."""
    _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    job_count = db.query(ProductJob).filter(
        ProductJob.product_id == product_id,
        ProductJob.status == "active",
    ).count()
    if not job_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No job map to assess against. Generate or author a job map first."
            ),
        )

    queue_service = QueueService(db)
    job = queue_service.create_job(
        job_type=QueueJobType.SELF_ASSESSMENT,
        input_data={"product_id": product_id},
        product_id=product_id,
        user_id=current_user.id,
    )
    send_task('self_assessment_task', job.id)

    return {
        "job_id": job.id,
        "job_uuid": job.job_uuid,
        "status": job.status.value,
        "message": "Self-assessment queued",
    }


@router.get("/{product_id}/self-assessment")
def get_self_assessment(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return the latest self-assessment, or nulls when none has been run."""
    _verify_product_access(db, product_id, current_user)

    assessment = _latest_self_assessment(db, product_id)
    if not assessment:
        return {
            "product_id": product_id,
            "assessment": None,
            "message": "No self-assessment yet. Competitor positions cannot be derived without one.",
        }

    return {"product_id": product_id, "assessment": assessment.to_dict()}


@router.get("/{product_id}/job-coverage")
def get_job_coverage(
    product_id: int,
    stale_after_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Our score beside every tracked competitor's, one row per job.

    A plain join over the self-assessment and whatever audits have run. Competitors
    without an audit are listed so their absence is visible rather than silently
    narrowing the comparison — an empty column is a prompt to run an audit, whereas a
    missing column looks like a competitor that does not exist.
    """
    _verify_product_access(db, product_id, current_user)

    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    jobs = db.query(ProductJob).filter(
        ProductJob.product_id == product_id,
        ProductJob.status == "active",
    ).all()

    competitors = db.query(ProductCompetitor).filter(
        ProductCompetitor.product_id == product_id,
        ProductCompetitor.tracked == True,  # noqa: E712 — SQLAlchemy needs ==
        ProductCompetitor.status == "active",
    ).all()

    reports = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_id == product_id
    ).all()
    reports_by_competitor = {r.product_competitor_id: r for r in reports}

    assessment = _latest_self_assessment(db, product_id)
    self_by_job: Dict[str, Dict[str, Any]] = {
        entry.get("job_id"): entry
        for entry in ((assessment.job_assessments or []) if assessment else [])
        if isinstance(entry, dict) and entry.get("job_id")
    }

    # Corroboration is what can rescue a low-confidence self-score: a job carrying real
    # customer signal is grounded even when the map entry itself came from product copy.
    corroboration = signal_counts(db, product_id)

    # A human judgement is only evidence if you can see whose it is. reviewed_by is
    # stored as a bare user id and has never surfaced anywhere, which makes an override
    # unattributable — resolve it once here rather than per cell.
    reviewer_ids = {
        entry.get("reviewed_by")
        for report in reports
        for entry in (report.job_assessments or [])
        if isinstance(entry, dict) and entry.get("reviewed_by")
    }
    reviewers = {
        u.id: (u.full_name or u.username)
        for u in (
            db.query(User).filter(User.id.in_(reviewer_ids)).all() if reviewer_ids else []
        )
    }

    now = datetime.now(timezone.utc)
    competitor_columns: List[Dict[str, Any]] = []
    assessments_by_competitor: Dict[int, Dict[str, Dict[str, Any]]] = {}

    for competitor in competitors:
        report = reports_by_competitor.get(competitor.id)
        generated_at = report.generated_at if report else None

        age_days = None
        if generated_at:
            # generated_at may come back naive from SQLite; treat it as UTC rather than
            # failing the whole view on a timezone comparison.
            reference = (
                generated_at if generated_at.tzinfo else generated_at.replace(tzinfo=timezone.utc)
            )
            age_days = (now - reference).days

        competitor_columns.append({
            "competitor_id": competitor.id,
            "competitor_name": competitor.competitor_name,
            "audited": report is not None,
            "audited_at": generated_at.isoformat() if generated_at else None,
            "audit_age_days": age_days,
            "stale": age_days is not None and age_days > stale_after_days,
            "report_version": report.report_version if report else None,
        })

        assessments_by_competitor[competitor.id] = {
            entry.get("job_id"): entry
            for entry in ((report.job_assessments or []) if report else [])
            if isinstance(entry, dict) and entry.get("job_id")
        }

    rows = []
    for job in jobs:
        self_entry = self_by_job.get(job.job_id_key) or {}

        cells = []
        for competitor in competitors:
            entry = assessments_by_competitor.get(competitor.id, {}).get(job.job_id_key)
            if not entry:
                cells.append({
                    "competitor_id": competitor.id,
                    "assessed": False,
                })
                continue
            grounded, withheld_reason = verdict_grounding(
                self_entry.get("confidence"),
                (corroboration.get(job.job_id_key) or {}).get("total", 0),
                entry.get("human_position"),
            )
            cells.append({
                "competitor_id": competitor.id,
                "assessed": True,
                "competitor_score": entry.get("competitor_score"),
                "system_position": entry.get("system_position"),
                # The verdict is a claim about how we compare, and it is only as good as
                # our own score. Withheld where ours is ungrounded — the competitor's
                # score is researched independently and still reported at full strength.
                "verdict_shown": grounded,
                "verdict_withheld_reason": withheld_reason,
                # Authoritative for display where a PM has overridden; the system
                # verdict is kept alongside rather than replaced.
                "human_position": entry.get("human_position"),
                "review_stale": entry.get("review_stale", False),
                "review_note": entry.get("review_note"),
                "reviewed_by_name": reviewers.get(entry.get("reviewed_by")),
                "reviewed_at": entry.get("reviewed_at"),
                "confidence": entry.get("confidence"),
            })

        # A PM who judges the comparison on this job has applied knowledge the product
        # description does not contain, which is what our score was missing. So their
        # call grounds the row, not just the cell it was made on.
        human_entries = [
            e for e in (
                assessments_by_competitor.get(c.id, {}).get(job.job_id_key)
                for c in competitors
            )
            if e and e.get("human_position")
        ]
        our_score_grounded, our_score_reason = verdict_grounding(
            self_entry.get("confidence"),
            (corroboration.get(job.job_id_key) or {}).get("total", 0),
            "reviewed" if human_entries else None,
        )
        # Say whose judgement it rests on. "Grounded by a human" is not evidence;
        # "grounded by A.G. Lambert on 28 Aug" is something a reader can weigh or chase.
        grounded_by = sorted({
            name for name in (
                reviewers.get(e.get("reviewed_by")) for e in human_entries
            ) if name
        })

        rows.append({
            "our_score_grounded": our_score_grounded,
            "our_score_withheld_reason": our_score_reason,
            "our_score_grounded_by": grounded_by,
            "job_id": job.job_id_key,
            "job_statement": job.statement,
            "job_type": job.job_type.value if job.job_type else None,
            "importance": job.importance.value if job.importance else None,
            "serve_intent": job.serve_intent,
            "provenance": job.provenance,
            "our_score": self_entry.get("score"),
            "our_confidence": self_entry.get("confidence"),
            "corroborating_signals": (corroboration.get(job.job_id_key) or {}).get("total", 0),
            "competitors": cells,
        })

    return {
        "product_id": product_id,
        "product_name": product.product_name,
        "jobs": rows,
        "competitors": competitor_columns,
        # How circular the map is. Belongs on this response specifically because this is
        # where the misleading conclusion gets drawn: a reader seeing high scores across
        # the board needs to know whether the jobs came from the product's own
        # description, which would make those scores near-tautological.
        "map_health": map_health(db, product_id),
        "self_assessment": {
            "exists": assessment is not None,
            "version": assessment.assessment_version if assessment else None,
            "assessed_at": (
                assessment.generated_at.isoformat()
                if assessment and assessment.generated_at else None
            ),
            # Whether independent evidence informed our own scores. Without it the job
            # map and the assessment both trace to the product's own description, so the
            # whole "us" column is self-referential and should be read that way.
            "evidence_based": assessment.evidence_based if assessment else None,
        },
    }


# ---------------------------------------------------------------------------
# Review: agree with or override a system verdict
# ---------------------------------------------------------------------------

# A human may only assert a real position. `unknown` is what the system says when it
# cannot compare, which is never something a person needs to claim.
REVIEWABLE_POSITIONS = {"advantage", "gap", "parity", "differentiator"}


class JobAssessmentReviewRequest(BaseModel):
    """Agree with, override, or clear a review on one job assessment."""
    action: str = Field(description="agree, override, or clear")
    position: Optional[str] = Field(
        default=None,
        description="Required for override: advantage, gap, parity, or differentiator"
    )
    note: Optional[str] = Field(default=None, description="Optional reason for the reviewer")


@router.post(
    "/{product_id}/competitors/{competitor_id}/job-assessments/{job_id}/review"
)
def review_job_assessment(
    product_id: int,
    competitor_id: int,
    job_id: str,
    body: JobAssessmentReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Record a PM's judgement on one (job, competitor) assessment.

    Three states, and the difference between the first two matters:

    - unreviewed  — nobody has looked. `reviewed_at` is null.
    - agreed      — reviewed and the system verdict stands. `human_position` stays null,
                    because the PM asserted nothing of their own; recording their
                    agreement as an override would freeze today's verdict against future
                    re-derivation.
    - overridden  — reviewed and corrected. `human_position` is authoritative for display.

    Capturing agreement separately is what stops the record being all negatives:
    corrections alone tell you where the model is wrong and never where it is right, and
    they cannot be told apart from "nobody looked".
    """
    _verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    action = (body.action or "").strip().lower()
    if action not in {"agree", "override", "clear"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="action must be one of: agree, override, clear",
        )

    if action == "override":
        if not body.position:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="position is required when overriding",
            )
        if body.position not in REVIEWABLE_POSITIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "position must be one of: "
                    + ", ".join(sorted(REVIEWABLE_POSITIONS))
                ),
            )

    report = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_id == product_id,
        CompetitorFunctionalReport.product_competitor_id == competitor_id,
    ).first()
    if not report or not report.job_assessments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No audit report for this competitor yet.",
        )

    assessments = list(report.job_assessments)
    target = next(
        (
            (i, a) for i, a in enumerate(assessments)
            if isinstance(a, dict) and a.get("job_id") == job_id
        ),
        None,
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' is not assessed in this competitor's report.",
        )

    index, entry = target
    updated = dict(entry)

    if action == "clear":
        # A PM who overrode by mistake needs a way back to the system verdict. This
        # returns the assessment to unreviewed rather than to "agreed" — clearing is not
        # an assertion that the verdict is right.
        updated["human_position"] = None
        updated["reviewed_at"] = None
        updated["reviewed_by"] = None
        updated["reviewed_job_statement"] = None
        updated["review_stale"] = False
        updated["review_note"] = None
    else:
        updated["human_position"] = body.position if action == "override" else None
        updated["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        updated["reviewed_by"] = current_user.id
        # Snapshot the wording judged against, so a later restatement can mark this
        # review stale rather than silently applying it to a different job.
        updated["reviewed_job_statement"] = updated.get("job_statement")
        updated["review_stale"] = False
        updated["review_note"] = body.note

    assessments[index] = updated
    report.job_assessments = assessments
    db.commit()

    return {
        "product_id": product_id,
        "competitor_id": competitor_id,
        "job_id": job_id,
        "action": action,
        "system_position": updated.get("system_position"),
        "human_position": updated.get("human_position"),
        "reviewed_at": updated.get("reviewed_at"),
        "review_stale": updated.get("review_stale", False),
    }


@router.get("/{product_id}/job-coverage/export")
def export_job_coverage(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Export the coverage matrix as markdown.

    The cross-competitor view is the one that goes into a planning deck, so it needs to
    leave the app. Rendered from the same data and the same withholding rule as the
    screen — a document read without the app beside it must not state a verdict the app
    itself declines to.
    """
    from fastapi.responses import PlainTextResponse

    _verify_access_or_404 = _verify_product_access(db, product_id, current_user)
    coverage = get_job_coverage(product_id, 30, db, current_user)

    lines = [
        f"# Job coverage — {coverage['product_name']}",
        "",
        f"_{len(coverage['competitors'])} tracked competitor(s). "
        f"Sorted by importance, then weakest coverage._",
        "",
    ]

    health = coverage["map_health"]
    if health["total_jobs"]:
        lines += [
            f"**Map health:** {health['independent_source_pct']}% of jobs have a source "
            f"other than the product description.",
            "",
        ]
    if coverage["self_assessment"]["evidence_based"] is False:
        lines += [
            "> Our scores rest only on the product description, which is also what the "
            "job map was generated from. Read them as the product's own claim rather "
            "than a measurement.",
            "",
        ]

    # Escape pipes in names too, not just statements — a competitor called "Foo|Bar"
    # would otherwise split the markdown table.
    def _cell(text) -> str:
        return str(text if text is not None else "—").replace("|", "\\|")

    names = [_cell(c["competitor_name"]) for c in coverage["competitors"]]
    lines.append("| Job | Importance | Us | " + " | ".join(names) + " |")
    lines.append("|---|---|---|" + "---|" * len(names))

    for row in coverage["jobs"]:
        cells = []
        for col in coverage["competitors"]:
            cell = next(
                (c for c in row["competitors"] if c["competitor_id"] == col["competitor_id"]),
                None,
            )
            if not cell or not cell.get("assessed"):
                cells.append("not audited")
                continue
            score = cell.get("competitor_score")
            human = cell.get("human_position")
            # Withholding applies to the derived verdict, which rests on our ungrounded
            # score. A PM's override is their own claim and owes nothing to it — dropping
            # it here would misrepresent their judgement as absent.
            if cell.get("verdict_shown") is False and not human:
                cells.append(f"{score} (no verdict)")
            else:
                verdict = human or cell.get("system_position") or "unknown"
                if human:
                    who = cell.get("reviewed_by_name") or "a reviewer"
                    marker = f" *({who}'s call)*"
                else:
                    marker = ""
                cells.append(f"{score} — {verdict}{marker}")

        grounded = any(
            c.get("assessed") and c.get("verdict_shown") is not False
            for c in row["competitors"]
        ) or not any(c.get("assessed") for c in row["competitors"])

        our = row["our_score"] if (grounded and row["our_score"] is not None) else "—"

        lines.append(
            f"| **{row['job_id']}** {_cell(row['job_statement'])} | "
            f"{_cell(row['importance'])} | {our} | "
            + " | ".join(cells)
            + " |"
        )

    lines += [
        "",
        "_Where no verdict is shown, our own score for that job is not grounded enough "
        "to compare. The competitor's score is researched independently and stands._",
        "",
        "_A verdict attributed to a person is their judgement, which is what grounds "
        "that row — the scores alone did not._",
    ]

    safe = (coverage["product_name"] or "product").replace(" ", "_")
    return PlainTextResponse(
        content="\n".join(lines),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={safe}_job_coverage.md"},
    )
