"""
Unified Synthesis API endpoints (Phase 3).

REST mirror of the unified-synthesis MCP tools. The unified synthesis
flow replaces the legacy landscape + opportunity synthesis pipeline.
"""

from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.competitor_intelligence import (
    CIProduct,
    ProductCompetitor,
    ProductPermissionLevel,
)
from app.models.queue import JobType
from app.models.synthesis import (
    SynthesisConfig,
    SynthesisReport,
    SynthesizedOpportunity,
)
from app.services.permission_service import PermissionService
from app.services.queue_service import QueueService
from app.utils.security import get_current_active_user
from app.utils.celery_utils import send_celery_task as send_task


router = APIRouter(
    prefix="/products",
    tags=["Unified Synthesis"],
)


VALID_SOURCE_TYPES = {"competitive", "customer", "internal", "evidence"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SynthesisConfigOut(BaseModel):
    product_id: int
    included_source_types: List[str]
    auto_generate_ideas: bool
    idea_priority_threshold: float
    scoring_weight_overrides: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None


class SynthesisConfigPut(BaseModel):
    source_types: Optional[List[str]] = Field(
        default=None,
        description="Subset of ['competitive','customer','internal','evidence'].",
    )
    auto_generate_ideas: Optional[bool] = None
    idea_priority_threshold: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="0.0-1.0; opportunities scoring above threshold*100 spawn ideas.",
    )
    scoring_weight_overrides: Optional[Dict[str, Any]] = None


class SynthesisRunResponse(BaseModel):
    job_id: int
    job_uuid: str
    status: str
    message: str


class SynthesisCompetitorEntry(BaseModel):
    competitor_id: int
    competitor_name: str
    competitor_url: Optional[str] = None
    audit_enabled: bool
    audit_status: Optional[str] = None
    audit_last_run: Optional[str] = None
    synthesis_included: bool


class SynthesisCompetitorsResponse(BaseModel):
    product_id: int
    competitors: List[SynthesisCompetitorEntry]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_access(
    db: Session,
    product_id: int,
    user: User,
    level: ProductPermissionLevel = ProductPermissionLevel.VIEW,
) -> CIProduct:
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not PermissionService(db).can_access_product(user.id, product_id, level):
        raise HTTPException(status_code=403, detail="Not authorized to access this product")
    return product


def _config_to_dict(config: SynthesisConfig) -> dict:
    return {
        "product_id": config.product_id,
        "included_source_types": list(config.included_source_types or []),
        "auto_generate_ideas": bool(config.auto_generate_ideas),
        "idea_priority_threshold": float(config.idea_priority_threshold or 0.7),
        "scoring_weight_overrides": config.scoring_weight_overrides,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


def _get_or_default_config(db: Session, product_id: int) -> dict:
    config = db.query(SynthesisConfig).filter(
        SynthesisConfig.product_id == product_id
    ).first()
    if config:
        return _config_to_dict(config)
    return {
        "product_id": product_id,
        "included_source_types": ["competitive"],
        "auto_generate_ideas": True,
        "idea_priority_threshold": 0.7,
        "scoring_weight_overrides": None,
        "updated_at": None,
    }


def _latest_report(db: Session, product_id: int) -> Optional[SynthesisReport]:
    return db.query(SynthesisReport).filter(
        SynthesisReport.product_id == product_id
    ).order_by(desc(SynthesisReport.report_version)).first()


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------

@router.get("/{product_id}/synthesis-config")
async def get_synthesis_config(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get the unified synthesis config (defaults shown if none persisted)."""
    _verify_access(db, product_id, current_user)
    config_dict = _get_or_default_config(db, product_id)
    exists = db.query(SynthesisConfig).filter(
        SynthesisConfig.product_id == product_id
    ).first() is not None
    return {"exists": exists, "config": config_dict}


@router.put("/{product_id}/synthesis-config")
async def put_synthesis_config(
    product_id: int,
    payload: SynthesisConfigPut,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create or update the unified SynthesisConfig (EDIT permission required)."""
    _verify_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    if payload.source_types is not None:
        if not payload.source_types:
            raise HTTPException(status_code=400, detail="source_types must be non-empty")
        unknown = [s for s in payload.source_types if s not in VALID_SOURCE_TYPES]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown source_types {unknown}. Allowed: {sorted(VALID_SOURCE_TYPES)}",
            )

    config = db.query(SynthesisConfig).filter(
        SynthesisConfig.product_id == product_id
    ).first()
    created = False
    if not config:
        config = SynthesisConfig(
            product_id=product_id,
            included_source_types=payload.source_types or ["competitive"],
            auto_generate_ideas=(
                payload.auto_generate_ideas if payload.auto_generate_ideas is not None else True
            ),
            idea_priority_threshold=(
                float(payload.idea_priority_threshold)
                if payload.idea_priority_threshold is not None else 0.7
            ),
            scoring_weight_overrides=payload.scoring_weight_overrides,
        )
        db.add(config)
        created = True
    else:
        if payload.source_types is not None:
            config.included_source_types = payload.source_types
        if payload.auto_generate_ideas is not None:
            config.auto_generate_ideas = bool(payload.auto_generate_ideas)
        if payload.idea_priority_threshold is not None:
            config.idea_priority_threshold = float(payload.idea_priority_threshold)
        if payload.scoring_weight_overrides is not None:
            config.scoring_weight_overrides = payload.scoring_weight_overrides

    db.commit()
    db.refresh(config)
    return {"created": created, "config": _config_to_dict(config)}


# ---------------------------------------------------------------------------
# Run + report endpoints
# ---------------------------------------------------------------------------

@router.post("/{product_id}/synthesis/run", status_code=status.HTTP_201_CREATED)
async def run_unified_synthesis(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Trigger a unified synthesis job (EDIT permission required)."""
    _verify_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    queue_service = QueueService(db)
    # Conflict check
    active = queue_service.get_active_jobs(product_id=product_id)
    if any(j.job_type == JobType.UNIFIED_SYNTHESIS for j in active):
        existing = next(
            j for j in active if j.job_type == JobType.UNIFIED_SYNTHESIS
        )
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Unified synthesis already in progress",
                "active_job_uuid": existing.job_uuid,
            },
        )

    job = queue_service.create_job(
        job_type=JobType.UNIFIED_SYNTHESIS,
        input_data={"product_id": product_id},
        product_id=product_id,
        user_id=current_user.id,
    )

    try:
        celery_result = send_task("app.queue.tasks.unified_synthesis_task", job.id)
        queue_service.mark_queued(job.id, celery_result.id)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to queue job: {str(e)}"
        )

    return SynthesisRunResponse(
        job_id=job.id,
        job_uuid=job.job_uuid,
        status="queued",
        message="Unified synthesis queued. Poll the job to track progress.",
    )


@router.get("/{product_id}/synthesis/latest")
async def get_latest_unified_report(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get the latest unified synthesis report for a product."""
    _verify_access(db, product_id, current_user)
    report = _latest_report(db, product_id)
    if not report:
        return {
            "product_id": product_id,
            "exists": False,
            "message": "No unified synthesis report yet. Run /synthesis/run first.",
        }
    return {
        "product_id": product_id,
        "exists": True,
        "synthesis_report_id": report.id,
        "report_version": report.report_version,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        "included_source_types": report.included_source_types,
        "source_stats": report.source_stats,
        "included_competitor_ids": report.included_competitor_ids,
        "source_competitor_report_ids": report.source_competitor_report_ids,
        "job_scorecard": report.job_scorecard,
        "feature_cluster_matrix": report.feature_cluster_matrix,
        "opportunities": report.opportunities,
        "high_impact_items": report.high_impact_items,
        "innovation_whitespace": report.innovation_whitespace,
        "analysis_summary": report.analysis_summary,
        "report_content_md": report.report_content_md,
        "changes_from_previous": report.changes_from_previous,
    }


@router.get("/{product_id}/synthesis/job-scorecard")
async def get_job_scorecard(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Per-job scorecard from the latest unified report."""
    _verify_access(db, product_id, current_user)
    report = _latest_report(db, product_id)
    if not report:
        raise HTTPException(status_code=404, detail="No unified synthesis report yet.")
    return {
        "product_id": product_id,
        "synthesis_report_id": report.id,
        "report_version": report.report_version,
        "job_scorecard": report.job_scorecard or [],
    }


@router.get("/{product_id}/synthesis/investment-recommendations")
async def get_investment_recommendations(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Per-job investment recommendations + rationale."""
    _verify_access(db, product_id, current_user)
    report = _latest_report(db, product_id)
    if not report:
        raise HTTPException(status_code=404, detail="No unified synthesis report yet.")

    recs = []
    for entry in (report.job_scorecard or []):
        recs.append({
            "job_id": entry.get("job_id"),
            "job_statement": entry.get("job_statement"),
            "importance": entry.get("importance"),
            "investment_recommendation": entry.get("investment_recommendation"),
            "rationale": entry.get("rationale"),
            "our_score": entry.get("our_score"),
            "best_in_class": entry.get("best_in_class"),
            "evidence_ids": entry.get("evidence_ids") or [],
        })
    return {
        "product_id": product_id,
        "synthesis_report_id": report.id,
        "report_version": report.report_version,
        "investment_recommendations": recs,
    }


@router.get("/{product_id}/synthesis/by-job/{job_id}")
async def get_synthesis_by_job(
    product_id: int,
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get scorecard entry, feature cluster, and opportunities for one job."""
    _verify_access(db, product_id, current_user)
    report = _latest_report(db, product_id)
    if not report:
        raise HTTPException(status_code=404, detail="No unified synthesis report yet.")

    scorecard_entry = next(
        (e for e in (report.job_scorecard or []) if e.get("job_id") == job_id),
        None,
    )
    feature_cluster = next(
        (c for c in (report.feature_cluster_matrix or []) if c.get("job_id") == job_id),
        None,
    )

    opps = db.query(SynthesizedOpportunity).filter(
        SynthesizedOpportunity.synthesis_report_id == report.id,
        SynthesizedOpportunity.job_id_key == job_id,
    ).order_by(SynthesizedOpportunity.priority_score.desc()).all()

    return {
        "product_id": product_id,
        "job_id": job_id,
        "synthesis_report_id": report.id,
        "report_version": report.report_version,
        "scorecard_entry": scorecard_entry,
        "feature_cluster": feature_cluster,
        "opportunities": [
            {
                "opportunity_id": o.id,
                "name": o.opportunity_name,
                "summary": o.opportunity_summary,
                "priority_score": o.priority_score,
                "source_count": o.source_count,
                "sources": o.sources,
                "recommended_action": o.recommended_action,
                "investment_tier": o.investment_tier,
                "job_satisfaction_delta": o.job_satisfaction_delta,
                "jtbd_statement": o.jtbd_statement,
                "feature_keywords": o.feature_keywords,
            }
            for o in opps
        ],
    }


@router.get(
    "/{product_id}/synthesis/competitors",
    response_model=SynthesisCompetitorsResponse,
)
async def get_synthesis_competitors(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List competitors with their audit/synthesis inclusion flags."""
    _verify_access(db, product_id, current_user)
    competitors = db.query(ProductCompetitor).filter(
        ProductCompetitor.product_id == product_id,
        ProductCompetitor.status == "active",
    ).all()

    return SynthesisCompetitorsResponse(
        product_id=product_id,
        competitors=[
            SynthesisCompetitorEntry(
                competitor_id=c.id,
                competitor_name=c.competitor_name,
                competitor_url=c.competitor_url,
                audit_enabled=bool(c.audit_enabled),
                audit_status=c.audit_status,
                audit_last_run=(
                    c.audit_last_run.isoformat() if c.audit_last_run else None
                ),
                synthesis_included=bool(c.synthesis_included),
            )
            for c in competitors
        ],
    )
