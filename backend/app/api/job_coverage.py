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
from app.services.queue_service import QueueService
from app.utils.celery_utils import send_celery_task as send_task
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
            cells.append({
                "competitor_id": competitor.id,
                "assessed": True,
                "competitor_score": entry.get("competitor_score"),
                "system_position": entry.get("system_position"),
                # Authoritative for display where a PM has overridden; the system
                # verdict is kept alongside rather than replaced.
                "human_position": entry.get("human_position"),
                "review_stale": entry.get("review_stale", False),
                "confidence": entry.get("confidence"),
            })

        rows.append({
            "job_id": job.job_id_key,
            "job_statement": job.statement,
            "job_type": job.job_type.value if job.job_type else None,
            "importance": job.importance.value if job.importance else None,
            "serve_intent": job.serve_intent,
            "provenance": job.provenance,
            "our_score": self_entry.get("score"),
            "our_confidence": self_entry.get("confidence"),
            "competitors": cells,
        })

    return {
        "product_id": product_id,
        "product_name": product.product_name,
        "jobs": rows,
        "competitors": competitor_columns,
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
