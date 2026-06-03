"""
Competitive Agents API endpoints.

This module provides REST API endpoints for the agent-centric competitive
intelligence system:
- Configuration management for CompetitiveAgentConfig
- V2 competitive analysis (functional audit + landscape synthesis)
- Competitor management and feature review
- Manual feature-to-idea workflow
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.database import get_db
from app.models.user import User
from app.models.queue import JobType, JobStatus
from app.models.competitor_intelligence import CIProduct, ProductCompetitor
from app.models.competitive_agent import (
    CompetitiveAgentConfig, AgentMode
)
from app.models.competitive_reports import (
    CompetitorFunctionalReport, CompetitorAlert
)
from app.models.idea import Idea, IdeaStatus, SourceType
from app.services.queue_service import QueueService
from app.services.permission_service import PermissionService
from app.services.competitive_report_metrics import count_gaps
from app.models.competitor_intelligence import ProductPermissionLevel
from app.utils.security import get_current_active_user, get_product_owner_or_admin
from app.utils.url import extract_domain

# Thread-safe task dispatch (see app/utils/celery_utils.py for explanation)
from app.utils.celery_utils import send_celery_task as send_task


router = APIRouter(
    prefix="/product-intelligence/agents",
    tags=["Competitive Agents"]
)


# ============================================================================
# Request/Response Schemas
# ============================================================================

class AgentConfigResponse(BaseModel):
    """Response schema for agent configuration."""
    id: int
    product_id: int

    # Product Analysis
    product_analysis_mode: str
    product_analysis_schedule: Optional[str]
    product_analysis_last_run: Optional[datetime]

    # Competitor Discovery
    competitor_discovery_mode: str
    competitor_discovery_schedule: Optional[str]
    competitor_discovery_last_run: Optional[datetime]
    alert_on_new_competitors: bool
    alert_on_disappeared_competitors: bool

    # Deep Analysis (V2: Functional Audit + Landscape Synthesis)
    deep_analysis_mode: str
    deep_analysis_schedule: Optional[str]
    deep_analysis_last_run: Optional[datetime]

    enabled: bool

    model_config = ConfigDict(from_attributes=True)


class AgentConfigUpdateRequest(BaseModel):
    """Request schema for updating agent configuration."""
    product_analysis_mode: Optional[str] = Field(None, pattern="^(manual|scheduled)$")
    product_analysis_schedule: Optional[str] = Field(None, pattern="^(daily|weekly|monthly)$")

    competitor_discovery_mode: Optional[str] = Field(None, pattern="^(manual|scheduled)$")
    competitor_discovery_schedule: Optional[str] = Field(None, pattern="^(daily|weekly|monthly)$")
    alert_on_new_competitors: Optional[bool] = None
    alert_on_disappeared_competitors: Optional[bool] = None

    deep_analysis_mode: Optional[str] = Field(None, pattern="^(manual|scheduled)$")
    deep_analysis_schedule: Optional[str] = Field(None, pattern="^(daily|weekly|monthly)$")

    enabled: Optional[bool] = None


class CompetitorResponse(BaseModel):
    """Response schema for competitor."""
    id: int
    product_id: int
    competitor_name: str
    competitor_url: Optional[str]
    status: str
    tracked: bool
    audit_status: Optional[str]
    audit_last_run: Optional[datetime]
    feature_count: int = 0
    evidence_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class FeatureResponse(BaseModel):
    """Response schema for competitor feature."""
    id: int
    product_competitor_id: int
    feature_name: str
    feature_description: Optional[str]
    feature_category: Optional[str]
    status: str
    cluster_id: Optional[int] = None
    cluster_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CreateIdeasRequest(BaseModel):
    """Request to create ideas from selected features."""
    feature_ids: List[int] = Field(..., min_length=1, max_length=20)


class AddCompetitorRequest(BaseModel):
    """Request to manually add a competitor."""
    competitor_name: str = Field(..., min_length=2, max_length=255)
    competitor_url: str = Field(..., min_length=5, max_length=500)


class FunctionalAuditRequest(BaseModel):
    """Optional parameters to scope a functional audit."""
    web_research: bool = True
    source_urls: Optional[List[str]] = None


class CompetitorAlertResponse(BaseModel):
    """Response schema for competitor alert."""
    id: int
    product_id: int
    alert_type: str
    competitor_id: Optional[int]
    competitor_name: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PricingAnalysisResponse(BaseModel):
    """Response schema for pricing analysis."""
    id: int
    product_competitor_id: int
    pricing_model: Optional[str]
    has_free_tier: bool
    has_trial: bool
    trial_days: Optional[int]
    pricing_tiers: Optional[list]
    has_enterprise: bool
    source_url: Optional[str]
    confidence: float
    analyzed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PositioningAnalysisResponse(BaseModel):
    """Response schema for positioning analysis."""
    id: int
    product_competitor_id: int
    tagline: Optional[str]
    value_propositions: Optional[list]
    target_audience: Optional[str]
    key_differentiators: Optional[list]
    positioning_statement: Optional[str]
    market_segment: Optional[str]
    confidence: float
    analyzed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MomentumAnalysisResponse(BaseModel):
    """Response schema for momentum analysis."""
    id: int
    product_competitor_id: int
    momentum_score: float
    momentum_trend: str
    customer_growth_trend: Optional[str]
    release_velocity: Optional[str]
    notable_customers: Optional[list]
    analysis_summary: Optional[str]
    confidence: float
    analyzed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChangeEventResponse(BaseModel):
    """Response schema for change event."""
    id: int
    product_competitor_id: int
    event_type: str
    event_title: str
    event_description: Optional[str]
    event_date: Optional[datetime]
    source_url: Optional[str]
    source_type: str
    impact_level: str
    detected_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FinancialsAnalysisResponse(BaseModel):
    """Response schema for financials analysis."""
    id: int
    product_competitor_id: int
    company_type: str
    total_funding: Optional[float]
    funding_stage: Optional[str]
    market_cap: Optional[float]
    revenue_ttm: Optional[float]
    employee_count: Optional[int]
    financial_health: str
    analysis_summary: Optional[str]
    confidence: float
    analyzed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    """Response schema for queued job."""
    job_id: int
    job_uuid: str
    job_type: str
    status: str
    message: str


# ============================================================================
# V2 Report Response Schemas (Functional Audit + Landscape Synthesis)
# ============================================================================

class FunctionalReportSummary(BaseModel):
    """Summary response for a competitor functional report."""
    id: int
    product_competitor_id: int
    product_id: int
    competitor_name: Optional[str] = None
    competitor_url: Optional[str] = None
    report_version: int
    features_compared: int = 0
    gaps_identified: int = 0
    generated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FunctionalReportDetail(BaseModel):
    """Detailed response for a competitor functional report."""
    id: int
    product_competitor_id: int
    product_id: int
    competitor_name: Optional[str] = None
    report_version: int
    report_content_md: Optional[str] = None
    competitor_context: Optional[dict] = None
    functional_comparison: Optional[List[dict]] = None
    gaps_deep_dive: Optional[List[dict]] = None
    technical_constraints: Optional[dict] = None
    generated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Helper Functions
# ============================================================================

def get_or_create_config(db: Session, product_id: int) -> CompetitiveAgentConfig:
    """Get existing config or create default one."""
    config = db.query(CompetitiveAgentConfig).filter(
        CompetitiveAgentConfig.product_id == product_id
    ).first()

    if not config:
        config = CompetitiveAgentConfig(product_id=product_id)
        db.add(config)
        db.commit()
        db.refresh(config)

    return config


def verify_product_access(
    db: Session,
    product_id: int,
    user: User,
    required_level: ProductPermissionLevel = ProductPermissionLevel.VIEW
) -> CIProduct:
    """Verify product exists and user has the required permission level.

    Uses PermissionService for consistent access control across all API files.
    Checks system admin bypass, product creator, team-wide access, and explicit grants.
    """
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=user.id,
        product_id=product_id,
        required_level=required_level
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this product"
        )
    return product


def get_competitor_or_404(
    db: Session, product_id: int, competitor_id: int
) -> ProductCompetitor:
    """Look up a competitor by ID, scoped to the given product. Raises 404 if not found."""
    competitor = db.query(ProductCompetitor).filter(
        ProductCompetitor.id == competitor_id,
        ProductCompetitor.product_id == product_id
    ).first()
    if not competitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Competitor {competitor_id} not found for product {product_id}"
        )
    return competitor


# ============================================================================
# Configuration Endpoints
# ============================================================================

@router.get("/{product_id}/config", response_model=AgentConfigResponse)
def get_agent_config(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get the competitive agent configuration for a product."""
    verify_product_access(db, product_id, current_user)
    config = get_or_create_config(db, product_id)

    return AgentConfigResponse(
        id=config.id,
        product_id=config.product_id,
        product_analysis_mode=config.product_analysis_mode.value if config.product_analysis_mode else "manual",
        product_analysis_schedule=config.product_analysis_schedule,
        product_analysis_last_run=config.product_analysis_last_run,
        competitor_discovery_mode=config.competitor_discovery_mode.value if config.competitor_discovery_mode else "manual",
        competitor_discovery_schedule=config.competitor_discovery_schedule,
        competitor_discovery_last_run=config.competitor_discovery_last_run,
        alert_on_new_competitors=config.alert_on_new_competitors,
        alert_on_disappeared_competitors=config.alert_on_disappeared_competitors,
        deep_analysis_mode=config.deep_analysis_mode.value if config.deep_analysis_mode else "manual",
        deep_analysis_schedule=config.deep_analysis_schedule,
        deep_analysis_last_run=config.deep_analysis_last_run,
        enabled=config.enabled
    )


@router.put("/{product_id}/config", response_model=AgentConfigResponse)
def update_agent_config(
    product_id: int,
    request: AgentConfigUpdateRequest,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Update the competitive agent configuration for a product."""
    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)
    config = get_or_create_config(db, product_id)

    # Update fields if provided
    if request.product_analysis_mode is not None:
        config.product_analysis_mode = AgentMode(request.product_analysis_mode)
    if request.product_analysis_schedule is not None:
        config.product_analysis_schedule = request.product_analysis_schedule
    if request.competitor_discovery_mode is not None:
        config.competitor_discovery_mode = AgentMode(request.competitor_discovery_mode)
    if request.competitor_discovery_schedule is not None:
        config.competitor_discovery_schedule = request.competitor_discovery_schedule
    if request.alert_on_new_competitors is not None:
        config.alert_on_new_competitors = request.alert_on_new_competitors
    if request.alert_on_disappeared_competitors is not None:
        config.alert_on_disappeared_competitors = request.alert_on_disappeared_competitors
    if request.deep_analysis_mode is not None:
        config.deep_analysis_mode = AgentMode(request.deep_analysis_mode)
    if request.deep_analysis_schedule is not None:
        config.deep_analysis_schedule = request.deep_analysis_schedule
    if request.enabled is not None:
        config.enabled = request.enabled

    db.commit()
    db.refresh(config)

    return get_agent_config(product_id, current_user, db)


# ============================================================================
# Competitor Alerts
# ============================================================================

@router.get("/{product_id}/alerts", response_model=List[CompetitorAlertResponse])
def get_competitor_alerts(
    product_id: int,
    unread_only: bool = Query(False, description="Only return unread alerts"),
    limit: int = Query(50, le=100, description="Max alerts to return"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get competitor alerts for a product."""
    verify_product_access(db, product_id, current_user)

    query = db.query(CompetitorAlert).filter(
        CompetitorAlert.product_id == product_id
    )

    if unread_only:
        query = query.filter(CompetitorAlert.is_read == False)

    alerts = query.order_by(CompetitorAlert.created_at.desc()).limit(limit).all()

    return [CompetitorAlertResponse(
        id=a.id,
        product_id=a.product_id,
        alert_type=a.alert_type,
        competitor_id=a.competitor_id,
        competitor_name=a.competitor_name,
        message=a.message,
        is_read=a.is_read,
        created_at=a.created_at
    ) for a in alerts]


@router.get("/{product_id}/alerts/count")
def get_unread_alert_count(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get count of unread alerts for a product."""
    verify_product_access(db, product_id, current_user)

    count = db.query(func.count(CompetitorAlert.id)).filter(
        CompetitorAlert.product_id == product_id,
        CompetitorAlert.is_read == False
    ).scalar()

    return {"unread_count": count}


@router.post("/{product_id}/alerts/{alert_id}/read")
def mark_alert_read(
    product_id: int,
    alert_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Mark an alert as read."""
    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)

    alert = db.query(CompetitorAlert).filter(
        CompetitorAlert.id == alert_id,
        CompetitorAlert.product_id == product_id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found"
        )

    alert.is_read = True
    db.commit()

    return {"message": f"Alert {alert_id} marked as read"}


@router.post("/{product_id}/alerts/read-all")
def mark_all_alerts_read(
    product_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Mark all alerts as read for a product."""
    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)

    updated = db.query(CompetitorAlert).filter(
        CompetitorAlert.product_id == product_id,
        CompetitorAlert.is_read == False
    ).update({CompetitorAlert.is_read: True})

    db.commit()

    return {"message": f"Marked {updated} alert(s) as read"}


# ============================================================================
# Product-Level Triggers
# ============================================================================

@router.post("/{product_id}/discover-competitors", response_model=JobResponse)
async def trigger_competitor_discovery(
    product_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Trigger async competitor discovery for a product."""
    product = verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)

    queue_service = QueueService(db)

    # Check for existing active job of this type for this product
    active_jobs = queue_service.get_active_jobs(product_id=product_id)
    existing_discovery = next(
        (j for j in active_jobs if j.job_type == JobType.COMPETITOR_DISCOVERY),
        None
    )
    if existing_discovery:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Competitor discovery already in progress (job {existing_discovery.job_uuid})"
        )

    job = queue_service.create_job(
        job_type=JobType.COMPETITOR_DISCOVERY,
        input_data={'product_id': product_id},
        product_id=product_id,
        user_id=current_user.id,
        auto_commit=False,  # Don't commit until Celery dispatch succeeds
    )

    # Queue the task - if this fails, rollback the job creation
    try:
        result = send_task('discover_competitors_task', job.id)
        job.celery_task_id = result.id
        job.status = JobStatus.QUEUED
        job.queued_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        db.rollback()
        import traceback
        print(f"[discover_competitors] Failed to queue task: {e}")
        print(f"[discover_competitors] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to queue task: {str(e)}. Please ensure Celery is running."
        )

    return JobResponse(
        job_id=job.id,
        job_uuid=job.job_uuid,
        job_type=job.job_type.value,
        status=job.status.value,
        message=f"Competitor discovery queued for product {product_id}"
    )


@router.post("/{product_id}/reanalyze-product", response_model=JobResponse)
def trigger_product_reanalysis(
    product_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Trigger async product reanalysis."""
    product = verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)

    queue_service = QueueService(db)

    # Check for existing active job of this type for this product
    active_jobs = queue_service.get_active_jobs(product_id=product_id)
    existing_analysis = next(
        (j for j in active_jobs if j.job_type == JobType.PRODUCT_ANALYSIS),
        None
    )
    if existing_analysis:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product analysis already in progress (job {existing_analysis.job_uuid})"
        )

    job = queue_service.create_job(
        job_type=JobType.PRODUCT_ANALYSIS,
        input_data={
            'product_name': product.product_name,
            'product_description': product.product_description,
            'source_type': product.product_source_type,
        },
        product_id=product_id,
        user_id=current_user.id,
        auto_commit=False,  # Don't commit until Celery dispatch succeeds
    )

    # Queue the task - if this fails, rollback the job creation
    try:
        result = send_task('analyze_product_task', job.id)
        job.celery_task_id = result.id
        job.status = JobStatus.QUEUED
        job.queued_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to queue task: {str(e)}. Please ensure Celery is running."
        )

    return JobResponse(
        job_id=job.id,
        job_uuid=job.job_uuid,
        job_type=job.job_type.value,
        status=job.status.value,
        message=f"Product reanalysis queued for product {product_id}"
    )


# ============================================================================
# Competitor Management
# ============================================================================

@router.get("/{product_id}/competitors", response_model=List[CompetitorResponse])
def list_competitors(
    product_id: int,
    tracked: Optional[bool] = Query(None, description="Filter by tracked status"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all competitors for a product."""
    verify_product_access(db, product_id, current_user)

    query = db.query(ProductCompetitor).filter(
        ProductCompetitor.product_id == product_id,
        ProductCompetitor.status == 'active'
    )

    if tracked is not None:
        query = query.filter(ProductCompetitor.tracked == tracked)

    competitors = query.all()

    # Get feature counts from functional reports (V2)
    from app.models.competitive_reports import CompetitorFunctionalReport
    from app.services.evidence_service import get_evidence_count_by_competitor

    # Get evidence counts in bulk
    evidence_counts = get_evidence_count_by_competitor(db, product_id)

    result = []
    for comp in competitors:
        # Count features from functional_comparison in latest report
        report = db.query(CompetitorFunctionalReport).filter(
            CompetitorFunctionalReport.product_competitor_id == comp.id
        ).order_by(CompetitorFunctionalReport.report_version.desc()).first()

        feature_count = 0
        if report and report.functional_comparison:
            feature_count = len(report.functional_comparison)

        result.append(CompetitorResponse(
            id=comp.id,
            product_id=comp.product_id,
            competitor_name=comp.competitor_name,
            competitor_url=comp.competitor_url,
            status=comp.status,
            tracked=comp.tracked or False,
            audit_status=comp.audit_status,
            audit_last_run=comp.audit_last_run,
            feature_count=feature_count,
            evidence_count=evidence_counts.get(comp.id, 0),
        ))

    return result


class CompetitorTrackedPatch(BaseModel):
    tracked: bool


@router.patch("/{product_id}/competitors/{competitor_id}/tracked", response_model=CompetitorResponse)
def patch_competitor_tracked(
    product_id: int,
    competitor_id: int,
    payload: CompetitorTrackedPatch,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Set or unset a competitor's tracked status."""
    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)
    competitor = get_competitor_or_404(db, product_id, competitor_id)

    competitor.tracked = payload.tracked
    db.commit()
    db.refresh(competitor)

    from app.models.competitive_reports import CompetitorFunctionalReport
    from app.services.evidence_service import get_evidence_count_by_competitor
    report = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_competitor_id == competitor.id
    ).order_by(CompetitorFunctionalReport.report_version.desc()).first()
    feature_count = len(report.functional_comparison) if report and report.functional_comparison else 0
    evidence_counts = get_evidence_count_by_competitor(db, product_id)

    return CompetitorResponse(
        id=competitor.id,
        product_id=competitor.product_id,
        competitor_name=competitor.competitor_name,
        competitor_url=competitor.competitor_url,
        status=competitor.status,
        tracked=competitor.tracked,
        audit_status=competitor.audit_status,
        audit_last_run=competitor.audit_last_run,
        feature_count=feature_count,
        evidence_count=evidence_counts.get(competitor.id, 0),
    )


@router.post("/{product_id}/competitors/{competitor_id}/deactivate")
def deactivate_competitor(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Soft-delete a competitor by setting status to inactive. Reports are preserved."""
    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)
    competitor = get_competitor_or_404(db, product_id, competitor_id)

    competitor.status = 'inactive'
    competitor.tracked = False
    db.commit()

    return {"message": f"Competitor {competitor_id} removed from list"}


@router.post("/{product_id}/competitors/add")
def add_competitor_manually(
    product_id: int,
    request: AddCompetitorRequest,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """
    Manually add a competitor not found via market discovery.

    Validates name+URL uniqueness within this product.
    Automatically enables deep analysis for manually added competitors.
    """
    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)

    # Check uniqueness within product - compare in Python for DB-agnostic behavior
    active_competitors = db.query(ProductCompetitor).filter(
        ProductCompetitor.product_id == product_id,
        ProductCompetitor.status == 'active'
    ).all()

    request_name_lower = request.competitor_name.lower()
    request_domain = extract_domain(request.competitor_url)

    for existing in active_competitors:
        if existing.competitor_name.lower() == request_name_lower:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A competitor named '{existing.competitor_name}' already exists for this product"
            )
        if request_domain and extract_domain(existing.competitor_url or '') == request_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A competitor with URL '{existing.competitor_url}' already exists for this product"
            )

    # Create the competitor
    competitor = ProductCompetitor(
        product_id=product_id,
        competitor_name=request.competitor_name,
        competitor_url=request.competitor_url,
        competitor_description=f"Manually added by {current_user.email}",
        tracked=True,  # Auto-track manually added competitors
        status='active'
    )
    db.add(competitor)
    db.commit()
    db.refresh(competitor)

    return {
        "id": competitor.id,
        "competitor_name": competitor.competitor_name,
        "competitor_url": competitor.competitor_url,
        "tracked": competitor.tracked,
        "message": f"Competitor '{competitor.competitor_name}' added successfully"
    }


# ============================================================================
# Per-Competitor Feature Review
# ============================================================================

@router.get("/{product_id}/competitors/{competitor_id}/features", response_model=List[FeatureResponse])
def list_competitor_features(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List features for a competitor from functional reports (V2).

    V2 Architecture: Reads from CompetitorFunctionalReport.functional_comparison
    instead of ProductCompetitorFeature table.
    """
    from app.models.competitive_reports import CompetitorFunctionalReport

    verify_product_access(db, product_id, current_user)
    get_competitor_or_404(db, product_id, competitor_id)

    # Get the latest functional report for this competitor
    report = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_competitor_id == competitor_id
    ).order_by(CompetitorFunctionalReport.report_version.desc()).first()

    result = []
    if report and report.functional_comparison:
        for idx, feature_data in enumerate(report.functional_comparison):
            feature_name = feature_data.get('competitor_feature_name', '')
            if not feature_name:
                continue

            result.append(FeatureResponse(
                id=idx + 1,  # Sequential ID since we don't have DB IDs
                product_competitor_id=competitor_id,
                feature_name=feature_name,
                feature_description=feature_data.get('functional_description', ''),
                feature_category=feature_data.get('feature_category', ''),
                status=feature_data.get('mapping_status', 'Gap'),  # Gap, Parity, etc.
            ))

    return result


@router.post("/{product_id}/competitors/{competitor_id}/features/{feature_index}/create-idea", response_model=JobResponse)
def create_idea_from_feature(
    product_id: int,
    competitor_id: int,
    feature_index: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """
    Create an idea from a single competitor feature (V2).

    V2 Architecture: Uses feature_index from functional_comparison array
    instead of ProductCompetitorFeature.id.
    """
    from app.models.competitive_reports import CompetitorFunctionalReport

    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)
    get_competitor_or_404(db, product_id, competitor_id)

    # Get the latest functional report
    report = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_competitor_id == competitor_id
    ).order_by(CompetitorFunctionalReport.report_version.desc()).first()

    if not report or not report.functional_comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No functional report found for this competitor"
        )

    # Get feature by index (1-based from API, 0-based in array)
    feature_idx = feature_index - 1
    if feature_idx < 0 or feature_idx >= len(report.functional_comparison):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature index {feature_index} not found"
        )

    feature_data = report.functional_comparison[feature_idx]
    feature_name = feature_data.get('competitor_feature_name', '')
    feature_description = feature_data.get('functional_description', '')

    # Get competitor name for context
    competitor = db.query(ProductCompetitor).filter(
        ProductCompetitor.id == competitor_id
    ).first()

    # Create idea directly
    idea = Idea(
        product_id=product_id,
        title=f"Add: {feature_name}",
        what_description=feature_description or f"Implement {feature_name} feature",
        why_description=f"Competitor '{competitor.competitor_name}' has this feature",
        use_case_description=f"Users would benefit from {feature_name}",
        status=IdeaStatus.PENDING,
        source_type=SourceType.COMPETITOR_AUTOMATED,
        source_metadata={
            'competitor_id': competitor_id,
            'competitor_name': competitor.competitor_name,
            'feature_index': feature_index,
            'feature_name': feature_name,
            'mapping_status': feature_data.get('mapping_status', '')
        },
        submitter_id=current_user.id
    )
    db.add(idea)
    db.commit()
    db.refresh(idea)

    # Queue triage
    queue_service = QueueService(db)
    job = queue_service.create_job(
        job_type=JobType.IDEA_TRIAGE,
        input_data={'idea_id': idea.id},
        product_id=product_id,
        user_id=current_user.id
    )
    db.commit()

    result = send_task('triage_idea_task', job.id)
    job.celery_task_id = result.id
    db.commit()

    return JobResponse(
        job_id=job.id,
        job_uuid=job.job_uuid,
        job_type=job.job_type.value,
        status=job.status.value,
        message=f"Idea created and triage queued for feature {feature_name}"
    )


@router.post("/{product_id}/competitors/{competitor_id}/features/create-ideas", response_model=List[JobResponse])
def create_ideas_from_features(
    product_id: int,
    competitor_id: int,
    request: CreateIdeasRequest,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """
    Create ideas from selected competitor features (V2).

    V2 Architecture: Uses feature_ids as indices into functional_comparison array.
    """
    from app.models.competitive_reports import CompetitorFunctionalReport

    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)
    get_competitor_or_404(db, product_id, competitor_id)

    competitor = db.query(ProductCompetitor).filter(
        ProductCompetitor.id == competitor_id
    ).first()

    # Get the latest functional report
    report = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_competitor_id == competitor_id
    ).order_by(CompetitorFunctionalReport.report_version.desc()).first()

    if not report or not report.functional_comparison:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No functional report found for this competitor"
        )

    results = []
    for feature_index in request.feature_ids:  # Now treated as indices
        # Convert 1-based index to 0-based
        feature_idx = feature_index - 1
        if feature_idx < 0 or feature_idx >= len(report.functional_comparison):
            continue

        feature_data = report.functional_comparison[feature_idx]
        feature_name = feature_data.get('competitor_feature_name', '')
        feature_description = feature_data.get('functional_description', '')

        if not feature_name:
            continue

        # Create idea
        idea = Idea(
            product_id=product_id,
            title=f"Add: {feature_name}",
            what_description=feature_description or f"Implement {feature_name} feature",
            why_description=f"Competitor '{competitor.competitor_name}' has this feature",
            use_case_description=f"Users would benefit from {feature_name}",
            status=IdeaStatus.PENDING,
            source_type=SourceType.COMPETITOR_AUTOMATED,
            source_metadata={
                'competitor_id': competitor_id,
                'competitor_name': competitor.competitor_name,
                'feature_index': feature_index,
                'feature_name': feature_name,
                'mapping_status': feature_data.get('mapping_status', '')
            },
            submitter_id=current_user.id
        )
        db.add(idea)
        db.flush()

        # Queue triage
        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.IDEA_TRIAGE,
            input_data={'idea_id': idea.id},
            product_id=product_id,
            user_id=current_user.id
        )

        results.append(JobResponse(
            job_id=job.id,
            job_uuid=job.job_uuid,
            job_type=job.job_type.value,
            status=job.status.value,
            message=f"Idea created for feature {feature_name}"
        ))

    db.commit()

    # Queue triage tasks
    for resp in results:
        send_task('triage_idea_task', resp.job_id)

    return results


# ============================================================================
# Strategic Analysis Results (DEPRECATED - V2 uses Functional Audit instead)
# These endpoints are deprecated and return 410 Gone.
# Use the V2 endpoints: /functional-reports, /landscape-report
# ============================================================================

@router.get("/{product_id}/competitors/{competitor_id}/pricing")
def get_pricing_analysis(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """DEPRECATED: Pricing analysis is no longer available. Use V2 functional audit instead."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This endpoint is deprecated. Use GET /{product_id}/competitors/{competitor_id}/functional-report instead."
    )


@router.get("/{product_id}/competitors/{competitor_id}/positioning")
def get_positioning_analysis(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """DEPRECATED: Positioning analysis is no longer available. Use V2 functional audit instead."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This endpoint is deprecated. Use GET /{product_id}/competitors/{competitor_id}/functional-report instead."
    )


@router.get("/{product_id}/competitors/{competitor_id}/changes")
def get_change_events(
    product_id: int,
    competitor_id: int,
    limit: int = Query(20, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """DEPRECATED: Change events tracking is no longer available. Use V2 functional audit instead."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This endpoint is deprecated. Use GET /{product_id}/competitors/{competitor_id}/functional-report instead."
    )


@router.get("/{product_id}/competitors/{competitor_id}/momentum")
def get_momentum_analysis(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """DEPRECATED: Momentum analysis is no longer available. Use V2 functional audit instead."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This endpoint is deprecated. Use GET /{product_id}/competitors/{competitor_id}/functional-report instead."
    )


@router.get("/{product_id}/competitors/{competitor_id}/financials")
def get_financials_analysis(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """DEPRECATED: Financials analysis is no longer available. Use V2 functional audit instead."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="This endpoint is deprecated. Use GET /{product_id}/competitors/{competitor_id}/functional-report instead."
    )


# ============================================================================
# V2 Competitive Analysis Endpoints (Functional Audit + Landscape Synthesis)
# ============================================================================

@router.post("/{product_id}/run-competitive-analysis-v2", response_model=JobResponse)
async def trigger_competitive_analysis_v2(
    product_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """
    Trigger V2 competitive analysis workflow.

    This runs the new two-step analysis pipeline:
    1. Functional audit for all active competitors (in parallel)
    2. Landscape opportunity synthesis (automatically after audits complete)
    3. Auto-export of all reports to filesystem

    Use this endpoint for comprehensive competitive analysis with
    feature comparison and opportunity identification.
    """
    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)

    queue_service = QueueService(db)

    # Check for existing active V2 analysis job
    active_jobs = queue_service.get_active_jobs(product_id=product_id)
    existing_v2 = next(
        (j for j in active_jobs if j.job_type in [
            JobType.FUNCTIONAL_AUDIT,
            JobType.LANDSCAPE_SYNTHESIS
        ]),
        None
    )
    if existing_v2:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"V2 competitive analysis already in progress (job {existing_v2.job_uuid})"
        )

    # Check for active competitors
    active_competitors = db.query(ProductCompetitor).filter(
        ProductCompetitor.product_id == product_id,
        ProductCompetitor.status == 'active'
    ).count()

    if active_competitors == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active competitors found. Add at least one competitor first."
        )

    # Create the orchestration job
    from app.models.queue import QueueJob
    job = QueueJob(
        job_type=JobType.SCHEDULED_DEEP_ANALYSIS,  # Reuse existing type for orchestration
        status=JobStatus.PENDING,
        product_id=product_id,
        user_id=current_user.id,
        input_data={
            'triggered_by': 'manual_v2',
            'competitors_count': active_competitors,
            'workflow': 'functional_audit_then_landscape_synthesis'
        }
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Queue the V2 orchestration task
    try:
        result = send_task('run_competitive_analysis_v2', job.id)
        job.celery_task_id = result.id
        job.status = JobStatus.QUEUED
        job.queued_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        db.rollback()
        import traceback
        print(f"[run_competitive_analysis_v2] Failed to queue task: {e}")
        print(f"[run_competitive_analysis_v2] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to queue task: {str(e)}. Please ensure Celery is running."
        )

    return JobResponse(
        job_id=job.id,
        job_uuid=job.job_uuid,
        job_type=job.job_type.value,
        status=job.status.value,
        message=f"V2 competitive analysis started for {active_competitors} competitors"
    )


@router.post("/{product_id}/competitors/{competitor_id}/functional-audit", response_model=JobResponse)
def trigger_functional_audit(
    product_id: int,
    competitor_id: int,
    request: FunctionalAuditRequest = None,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Trigger a functional audit for a single competitor.

    Optional body params:
    - web_research (default true): skip Brave web search if false.
    - source_urls (max 5): specific pages to fetch and feed to the agent.
    """
    from app.services.scoped_input_validator import validate_scoped_inputs, ScopedInputError

    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)
    get_competitor_or_404(db, product_id, competitor_id)

    web_research = True
    source_urls: list[str] = []
    if request is not None:
        try:
            source_urls = validate_scoped_inputs(request.source_urls)
        except ScopedInputError as err:
            raise HTTPException(status_code=400, detail=err.payload)
        web_research = request.web_research

    queue_service = QueueService(db)

    # Check for existing active audit for this competitor
    active_jobs = queue_service.get_active_jobs(product_id=product_id)
    existing_audit = next(
        (j for j in active_jobs
         if j.job_type == JobType.FUNCTIONAL_AUDIT
         and j.input_data.get('competitor_id') == competitor_id),
        None
    )
    if existing_audit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Functional audit already in progress for this competitor (job {existing_audit.job_uuid})"
        )

    # Create the job
    from app.models.queue import QueueJob
    job = QueueJob(
        job_type=JobType.FUNCTIONAL_AUDIT,
        status=JobStatus.PENDING,
        product_id=product_id,
        user_id=current_user.id,
        input_data={
            'competitor_id': competitor_id,
            'web_research_enabled': web_research,
            'source_urls': source_urls,
        }
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Queue the task
    try:
        result = send_task('functional_audit_task', job.id)
        job.celery_task_id = result.id
        job.status = JobStatus.QUEUED
        job.queued_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to queue task: {str(e)}. Please ensure Celery is running."
        )

    return JobResponse(
        job_id=job.id,
        job_uuid=job.job_uuid,
        job_type=job.job_type.value,
        status=job.status.value,
        message=f"Functional audit queued for competitor {competitor_id}"
    )


@router.post("/{product_id}/competitors/{competitor_id}/refresh-research")
def refresh_competitor_research(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db),
):
    """Force a re-fetch of cached web research for a competitor.

    Runs synchronously (~5s). Populates `cached_search_results` and
    `cached_search_at`. Subsequent audits within TTL will use the cache
    and skip Brave.
    """
    from app.models.competitor_intelligence import CIProduct, ProductFeature
    from app.services.competitor_research_cache import CompetitorResearchCache

    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)
    competitor = get_competitor_or_404(db, product_id, competitor_id)

    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    features = (
        db.query(ProductFeature)
        .filter(ProductFeature.product_id == product_id, ProductFeature.status == "active")
        .limit(15)
        .all()
    )
    product_context = {
        "product_name": product.product_name if product else "",
        "product_category": product.product_category if product else None,
        "core_features": [f.feature_name for f in features],
    }

    results = CompetitorResearchCache(db).refresh(competitor, product_context)

    return {
        "competitor_id": competitor.id,
        "competitor_name": competitor.competitor_name,
        "results_count": len(results),
        "cached_at": competitor.cached_search_at.isoformat() if competitor.cached_search_at else None,
    }


@router.get("/{product_id}/competitors/{competitor_id}/functional-report", response_model=Optional[FunctionalReportDetail])
def get_functional_report(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get the functional audit report for a competitor."""
    verify_product_access(db, product_id, current_user)
    competitor = get_competitor_or_404(db, product_id, competitor_id)

    report = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_competitor_id == competitor_id,
        CompetitorFunctionalReport.product_id == product_id
    ).first()

    if not report:
        return None

    return FunctionalReportDetail(
        id=report.id,
        product_competitor_id=report.product_competitor_id,
        product_id=report.product_id,
        competitor_name=competitor.competitor_name,
        report_version=report.report_version,
        report_content_md=report.report_content_md,
        competitor_context=report.competitor_context,
        functional_comparison=report.functional_comparison,
        gaps_deep_dive=report.gaps_deep_dive,
        technical_constraints=report.technical_constraints,
        generated_at=report.generated_at
    )


@router.get("/{product_id}/competitors/{competitor_id}/functional-report/export")
def export_functional_report(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Export the functional audit report as markdown."""
    from fastapi.responses import PlainTextResponse

    verify_product_access(db, product_id, current_user)
    competitor = get_competitor_or_404(db, product_id, competitor_id)

    report = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_competitor_id == competitor_id,
        CompetitorFunctionalReport.product_id == product_id
    ).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No functional report found for competitor {competitor_id}"
        )

    # Return markdown content
    return PlainTextResponse(
        content=report.report_content_md or "# No report content available",
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename={competitor.competitor_name.replace(' ', '_')}_functional_audit.md"
        }
    )


@router.get("/{product_id}/functional-reports", response_model=List[FunctionalReportSummary])
def list_functional_reports(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all functional reports for a product."""
    verify_product_access(db, product_id, current_user)

    reports = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_id == product_id
    ).all()

    result = []
    for report in reports:
        # Get competitor name
        competitor = db.query(ProductCompetitor).filter(
            ProductCompetitor.id == report.product_competitor_id
        ).first()

        features_compared = len(report.functional_comparison) if report.functional_comparison else 0
        gaps_identified = count_gaps(report)

        result.append(FunctionalReportSummary(
            id=report.id,
            product_competitor_id=report.product_competitor_id,
            product_id=report.product_id,
            competitor_name=competitor.competitor_name if competitor else None,
            competitor_url=competitor.competitor_url if competitor else None,
            report_version=report.report_version,
            features_compared=features_compared,
            gaps_identified=gaps_identified,
            generated_at=report.generated_at
        ))

    return result


class CreateGapIdeasRequest(BaseModel):
    """Request to create ideas from selected competitor gaps."""
    gap_indices: List[int] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Indices of gaps to create ideas from (0-indexed)"
    )


@router.post("/{product_id}/competitors/{competitor_id}/gaps/create-ideas", response_model=List[JobResponse])
def create_ideas_from_gaps(
    product_id: int,
    competitor_id: int,
    request: CreateGapIdeasRequest,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """
    Create ideas from selected competitor gaps.

    Creates ideas in the idea queue and triggers triage for each.
    Gaps that already have ideas created will be skipped.
    """
    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)

    # Get the functional report
    report = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_competitor_id == competitor_id,
        CompetitorFunctionalReport.product_id == product_id
    ).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No functional report found for this competitor. Run functional audit first."
        )

    if not report.gaps_deep_dive:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No gaps in the functional report."
        )

    # Get competitor name
    competitor = db.query(ProductCompetitor).filter(
        ProductCompetitor.id == competitor_id
    ).first()
    competitor_name = competitor.competitor_name if competitor else 'Unknown Competitor'

    # Validate indices
    max_index = len(report.gaps_deep_dive) - 1
    invalid_indices = [i for i in request.gap_indices if i < 0 or i > max_index]
    if invalid_indices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid gap indices: {invalid_indices}. Valid range: 0-{max_index}"
        )

    # Check which gaps already have ideas (via source_metadata lookup)
    # Filter in Python since SQLite doesn't support JSON path operators
    all_ideas = db.query(Idea).filter(
        Idea.product_id == product_id,
        Idea.source_type == SourceType.COMPETITOR_AUTOMATED
    ).all()

    existing_gap_indices = set()
    for idea in all_ideas:
        metadata = idea.source_metadata or {}
        if (metadata.get('source') == 'competitor_gap' and
            str(metadata.get('competitor_id')) == str(competitor_id)):
            gap_idx = metadata.get('gap_index')
            if gap_idx is not None:
                existing_gap_indices.add(gap_idx)

    # Create ideas from selected gaps (skipping already-created ones)
    results = []
    skipped = []
    queue_service = QueueService(db)

    for idx in request.gap_indices:
        if idx in existing_gap_indices:
            skipped.append(idx)
            continue

        gap = report.gaps_deep_dive[idx]
        feature_name = gap.get('feature_name', 'Unknown Feature')
        user_problem = gap.get('user_problem', '')
        evidence = gap.get('evidence', '')

        # Create idea
        idea = Idea(
            product_id=product_id,
            title=f"Add: {feature_name}",
            what_description=f"Implement {feature_name} similar to {competitor_name}'s offering.",
            why_description=user_problem,
            use_case_description=f"Based on competitive analysis of {competitor_name}: {evidence}",
            status=IdeaStatus.PENDING,
            source_type=SourceType.COMPETITOR_AUTOMATED,
            source_metadata={
                'source': 'competitor_gap',
                'competitor_id': competitor_id,
                'competitor_name': competitor_name,
                'gap_index': idx,
                'feature_name': feature_name,
                'functional_report_id': report.id
            },
            submitter_id=current_user.id
        )
        db.add(idea)
        db.flush()

        # Create triage job
        job = queue_service.create_job(
            job_type=JobType.IDEA_TRIAGE,
            input_data={'idea_id': idea.id},
            product_id=product_id,
            user_id=current_user.id
        )

        results.append(JobResponse(
            job_id=job.id,
            job_uuid=job.job_uuid,
            job_type=job.job_type.value,
            status=job.status.value,
            message=f"Idea created for gap: {feature_name}"
        ))

    db.commit()

    # Queue triage tasks
    for resp in results:
        send_task('triage_idea_task', resp.job_id)

    # Add note about skipped gaps to last result
    if skipped and results:
        results[-1].message += f" (Skipped {len(skipped)} gap(s) with existing ideas)"
    elif skipped and not results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"All selected gaps already have ideas created. Skipped indices: {skipped}"
        )

    return results


@router.get("/{product_id}/competitors/{competitor_id}/gaps/{gap_index}/idea-status")
def get_gap_idea_status(
    product_id: int,
    competitor_id: int,
    gap_index: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Check if an idea has been created from a specific competitor gap.

    Returns idea_created: true/false and idea_id if exists.
    """
    verify_product_access(db, product_id, current_user)

    # Look for existing idea - filter in Python since SQLite doesn't support JSON path operators
    all_ideas = db.query(Idea).filter(
        Idea.product_id == product_id,
        Idea.source_type == SourceType.COMPETITOR_AUTOMATED
    ).all()

    existing_idea = None
    for idea in all_ideas:
        metadata = idea.source_metadata or {}
        if (metadata.get('source') == 'competitor_gap' and
            str(metadata.get('competitor_id')) == str(competitor_id) and
            str(metadata.get('gap_index')) == str(gap_index)):
            existing_idea = idea
            break

    return {
        'idea_created': existing_idea is not None,
        'idea_id': existing_idea.id if existing_idea else None
    }


@router.get("/{product_id}/competitors/{competitor_id}/gaps/idea-statuses")
def get_all_gap_idea_statuses(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get idea status for all gaps in a competitor's functional report.

    Returns a dictionary mapping gap indices to their idea status.
    Useful for batch loading the UI with idea badges.
    """
    verify_product_access(db, product_id, current_user)

    # Get all competitor automated ideas for this product
    # Filter in Python since SQLite doesn't support JSON path operators
    all_ideas = db.query(Idea).filter(
        Idea.product_id == product_id,
        Idea.source_type == SourceType.COMPETITOR_AUTOMATED
    ).all()

    # Build status map by filtering for competitor gap ideas
    status_map = {}
    for idea in all_ideas:
        metadata = idea.source_metadata or {}
        if (metadata.get('source') == 'competitor_gap' and
            str(metadata.get('competitor_id')) == str(competitor_id)):
            gap_idx = metadata.get('gap_index')
            if gap_idx is not None:
                status_map[gap_idx] = {
                    'idea_created': True,
                    'idea_id': idea.id
                }

    return {
        'statuses': status_map,
        'total_ideas_created': len(status_map)
    }


class ExportGapsRequest(BaseModel):
    """Request to export selected competitor gaps as JSON."""
    gap_indices: List[int] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Indices of gaps to export (0-indexed)"
    )


@router.post("/{product_id}/competitors/{competitor_id}/gaps/export-json")
def export_gaps_json(
    product_id: int,
    competitor_id: int,
    request: ExportGapsRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Export selected competitor gaps as JSON.

    Returns a portable JSON format suitable for import into
    external roadmap or backlog management tools.
    """
    from fastapi.responses import JSONResponse

    verify_product_access(db, product_id, current_user)

    # Get product name
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )

    # Get competitor name
    competitor = db.query(ProductCompetitor).filter(
        ProductCompetitor.id == competitor_id
    ).first()
    if not competitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Competitor not found"
        )

    # Get the functional report
    report = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_competitor_id == competitor_id,
        CompetitorFunctionalReport.product_id == product_id
    ).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No functional report found for this competitor."
        )

    if not report.gaps_deep_dive:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No gaps in the functional report."
        )

    # Validate indices
    max_index = len(report.gaps_deep_dive) - 1
    invalid_indices = [i for i in request.gap_indices if i < 0 or i > max_index]
    if invalid_indices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid gap indices: {invalid_indices}. Valid range: 0-{max_index}"
        )

    # Build export data for selected gaps
    selected_gaps = [
        report.gaps_deep_dive[idx]
        for idx in request.gap_indices
    ]

    export_data = {
        "version": "1.0",
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        "product_id": product_id,
        "product_name": product.product_name,
        "competitor_id": competitor_id,
        "competitor_name": competitor.competitor_name,
        "gaps": selected_gaps,
        "metadata": {
            "total_gaps_in_report": len(report.gaps_deep_dive),
            "exported_count": len(selected_gaps),
            "report_version": report.report_version,
        }
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f"attachment; filename={competitor.competitor_name.replace(' ', '_')}_gaps_v{report.report_version}.json"
        }
    )
