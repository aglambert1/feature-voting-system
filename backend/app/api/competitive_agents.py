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
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User, UserRole
from app.models.queue import JobType, JobStatus
from app.models.competitor_intelligence import CIProduct, ProductCompetitor
from app.models.competitive_agent import (
    CompetitiveAgentConfig, AgentMode
)
from app.models.competitive_reports import (
    CompetitorFunctionalReport, LandscapeOpportunityReport, CompetitorAlert
)
from app.models.idea import Idea, IdeaStatus, SourceType
from app.services.queue_service import QueueService
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

    # Idea Auto-Generation Settings
    intensity_similarity_threshold: float  # DEPRECATED - kept for backwards compatibility
    intensity_idea_threshold: float  # Priority score threshold (0.0-1.0)

    enabled: bool

    class Config:
        from_attributes = True


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

    intensity_similarity_threshold: Optional[float] = Field(None, ge=0.5, le=0.95)  # DEPRECATED
    intensity_idea_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)  # Priority threshold (0.0 = disabled)

    enabled: Optional[bool] = None


class CompetitorResponse(BaseModel):
    """Response schema for competitor."""
    id: int
    product_id: int
    competitor_name: str
    competitor_url: Optional[str]
    status: str
    deep_analysis_enabled: bool
    deep_analysis_status: Optional[str]
    deep_analysis_last_run: Optional[datetime]
    feature_count: int = 0

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class CreateIdeasRequest(BaseModel):
    """Request to create ideas from selected features."""
    feature_ids: List[int] = Field(..., min_length=1, max_length=20)


class AddCompetitorRequest(BaseModel):
    """Request to manually add a competitor."""
    competitor_name: str = Field(..., min_length=2, max_length=255)
    competitor_url: str = Field(..., min_length=5, max_length=500)


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


class LandscapeReportSummary(BaseModel):
    """Summary response for a landscape opportunity report."""
    id: int
    product_id: int
    report_version: int
    feature_clusters_count: int = 0
    feature_opportunities_count: int = 0
    high_impact_gaps_count: int = 0
    source_competitor_report_ids: Optional[List[int]] = None
    generated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LandscapeReportDetail(BaseModel):
    """Detailed response for a landscape opportunity report."""
    id: int
    product_id: int
    report_version: int
    report_content_md: Optional[str] = None
    feature_cluster_matrix: Optional[List[dict]] = None
    feature_opportunities: Optional[List[dict]] = None
    high_impact_gaps: Optional[List[dict]] = None
    source_competitor_report_ids: Optional[List[int]] = None
    generated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FeatureOpportunitiesExportResponse(BaseModel):
    """Response for portable feature opportunities JSON export."""
    version: str = "1.0"
    generated_at: str
    product_id: int
    product_name: Optional[str] = None
    feature_ideas: List[dict]
    metadata: dict


class CreateIdeasFromOpportunitiesRequest(BaseModel):
    """Request to create ideas from selected feature opportunities."""
    opportunity_indices: List[int] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Indices of feature opportunities to create ideas from (0-indexed)"
    )


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


def verify_product_access(db: Session, product_id: int, user: User) -> CIProduct:
    """Verify product exists and user has ownership access.

    Admin users can access any product. Product Owners can only access
    products they created. Returns 403 if the user lacks access.
    """
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )
    if user.role != UserRole.ADMIN and product.created_by_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this product"
        )
    return product


def verify_competitor_access(
    db: Session, product_id: int, competitor_id: int, user: User
) -> ProductCompetitor:
    """Verify competitor exists and belongs to product."""
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
        intensity_similarity_threshold=config.intensity_similarity_threshold,
        intensity_idea_threshold=config.intensity_idea_threshold,
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
    verify_product_access(db, product_id, current_user)
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
    if request.intensity_similarity_threshold is not None:
        config.intensity_similarity_threshold = request.intensity_similarity_threshold
    if request.intensity_idea_threshold is not None:
        config.intensity_idea_threshold = request.intensity_idea_threshold
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
    verify_product_access(db, product_id, current_user)

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
    verify_product_access(db, product_id, current_user)

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
    product = verify_product_access(db, product_id, current_user)

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
    product = verify_product_access(db, product_id, current_user)

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
    deep_analysis_enabled: Optional[bool] = Query(None, description="Filter by deep analysis enabled"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all competitors for a product."""
    verify_product_access(db, product_id, current_user)

    query = db.query(ProductCompetitor).filter(
        ProductCompetitor.product_id == product_id,
        ProductCompetitor.status == 'active'
    )

    if deep_analysis_enabled is not None:
        query = query.filter(ProductCompetitor.deep_analysis_enabled == deep_analysis_enabled)

    competitors = query.all()

    # Get feature counts from functional reports (V2)
    from app.models.competitive_reports import CompetitorFunctionalReport

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
            deep_analysis_enabled=comp.deep_analysis_enabled or False,
            deep_analysis_status=comp.deep_analysis_status,
            deep_analysis_last_run=comp.deep_analysis_last_run,
            feature_count=feature_count
        ))

    return result


@router.post("/{product_id}/competitors/{competitor_id}/enable-deep-analysis")
def enable_deep_analysis(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Mark a competitor for deep analysis."""
    competitor = verify_competitor_access(db, product_id, competitor_id, current_user)

    competitor.deep_analysis_enabled = True
    db.commit()

    return {"message": f"Deep analysis enabled for competitor {competitor_id}"}


@router.post("/{product_id}/competitors/{competitor_id}/disable-deep-analysis")
def disable_deep_analysis(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Remove a competitor from deep analysis."""
    competitor = verify_competitor_access(db, product_id, competitor_id, current_user)

    competitor.deep_analysis_enabled = False
    db.commit()

    return {"message": f"Deep analysis disabled for competitor {competitor_id}"}


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
    verify_product_access(db, product_id, current_user)

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
        deep_analysis_enabled=True,  # Auto-enable for manually added
        status='active'
    )
    db.add(competitor)
    db.commit()
    db.refresh(competitor)

    return {
        "id": competitor.id,
        "competitor_name": competitor.competitor_name,
        "competitor_url": competitor.competitor_url,
        "deep_analysis_enabled": competitor.deep_analysis_enabled,
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

    verify_competitor_access(db, product_id, competitor_id, current_user)

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

    verify_competitor_access(db, product_id, competitor_id, current_user)

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

    verify_competitor_access(db, product_id, competitor_id, current_user)

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
    verify_product_access(db, product_id, current_user)

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
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Trigger a functional audit for a single competitor."""
    verify_competitor_access(db, product_id, competitor_id, current_user)

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
        input_data={'competitor_id': competitor_id}
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


@router.get("/{product_id}/competitors/{competitor_id}/functional-report", response_model=Optional[FunctionalReportDetail])
def get_functional_report(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get the functional audit report for a competitor."""
    competitor = verify_competitor_access(db, product_id, competitor_id, current_user)

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

    competitor = verify_competitor_access(db, product_id, competitor_id, current_user)

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
        gaps_identified = len(report.gaps_deep_dive) if report.gaps_deep_dive else 0

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
    verify_product_access(db, product_id, current_user)

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


@router.post("/{product_id}/run-landscape-synthesis", response_model=JobResponse)
def trigger_landscape_synthesis(
    product_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """
    Trigger landscape opportunity synthesis.

    This synthesizes all existing functional audit reports into
    a comprehensive landscape analysis with feature opportunities.

    Requires at least one functional report to exist.
    """
    verify_product_access(db, product_id, current_user)

    # Check for existing functional reports
    report_count = db.query(CompetitorFunctionalReport).filter(
        CompetitorFunctionalReport.product_id == product_id
    ).count()

    if report_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No functional reports found. Run functional audits first."
        )

    queue_service = QueueService(db)

    # Check for existing active synthesis job
    active_jobs = queue_service.get_active_jobs(product_id=product_id)
    existing_synthesis = next(
        (j for j in active_jobs if j.job_type == JobType.LANDSCAPE_SYNTHESIS),
        None
    )
    if existing_synthesis:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Landscape synthesis already in progress (job {existing_synthesis.job_uuid})"
        )

    # Create the job
    from app.models.queue import QueueJob
    job = QueueJob(
        job_type=JobType.LANDSCAPE_SYNTHESIS,
        status=JobStatus.PENDING,
        product_id=product_id,
        user_id=current_user.id,
        input_data={'functional_report_count': report_count}
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Queue the task
    try:
        result = send_task('landscape_synthesis_task', job.id)
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
        message=f"Landscape synthesis queued for {report_count} competitor reports"
    )


@router.get("/{product_id}/landscape-report", response_model=Optional[LandscapeReportDetail])
def get_landscape_report(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get the landscape opportunity report for a product."""
    verify_product_access(db, product_id, current_user)

    report = db.query(LandscapeOpportunityReport).filter(
        LandscapeOpportunityReport.product_id == product_id
    ).first()

    if not report:
        return None

    return LandscapeReportDetail(
        id=report.id,
        product_id=report.product_id,
        report_version=report.report_version,
        report_content_md=report.report_content_md,
        feature_cluster_matrix=report.feature_cluster_matrix,
        feature_opportunities=report.feature_opportunities,
        high_impact_gaps=report.high_impact_gaps,
        source_competitor_report_ids=report.source_competitor_report_ids,
        generated_at=report.generated_at
    )


@router.get("/{product_id}/landscape-report/feature-opportunities", response_model=Optional[FeatureOpportunitiesExportResponse])
def get_feature_opportunities_export(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get portable JSON export of feature opportunities."""
    product = verify_product_access(db, product_id, current_user)

    report = db.query(LandscapeOpportunityReport).filter(
        LandscapeOpportunityReport.product_id == product_id
    ).first()

    if not report:
        return None

    return FeatureOpportunitiesExportResponse(
        version="1.0",
        generated_at=report.generated_at.isoformat() if report.generated_at else datetime.utcnow().isoformat(),
        product_id=product_id,
        product_name=product.product_name,
        feature_ideas=report.feature_opportunities or [],
        metadata={
            'report_version': report.report_version,
            'source_report_ids': report.source_competitor_report_ids,
            'total_opportunities': len(report.feature_opportunities) if report.feature_opportunities else 0
        }
    )


@router.post("/{product_id}/landscape-report/create-ideas", response_model=List[JobResponse])
def create_ideas_from_opportunities(
    product_id: int,
    request: CreateIdeasFromOpportunitiesRequest,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """
    Create ideas from selected feature opportunities.

    Creates ideas in the idea queue and triggers triage for each.
    Opportunities that already have ideas created will be skipped.
    """
    verify_product_access(db, product_id, current_user)

    # Get the landscape report
    report = db.query(LandscapeOpportunityReport).filter(
        LandscapeOpportunityReport.product_id == product_id
    ).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No landscape report found. Run landscape synthesis first."
        )

    if not report.feature_opportunities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No feature opportunities in the landscape report."
        )

    # Validate indices
    max_index = len(report.feature_opportunities) - 1
    invalid_indices = [i for i in request.opportunity_indices if i < 0 or i > max_index]
    if invalid_indices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid opportunity indices: {invalid_indices}. Valid range: 0-{max_index}"
        )

    # Check which opportunities already have ideas (via source_metadata lookup)
    # Filter in Python since SQLite doesn't support JSON path operators
    all_ideas = db.query(Idea).filter(
        Idea.product_id == product_id,
        Idea.source_type == SourceType.COMPETITOR_AUTOMATED
    ).all()

    existing_opp_indices = set()
    for idea in all_ideas:
        metadata = idea.source_metadata or {}
        if metadata.get('source') == 'landscape_synthesis':
            opp_idx = metadata.get('opportunity_index')
            if opp_idx is not None:
                existing_opp_indices.add(opp_idx)

    # Create ideas from selected opportunities (skipping already-created ones)
    results = []
    skipped = []
    queue_service = QueueService(db)

    for idx in request.opportunity_indices:
        if idx in existing_opp_indices:
            skipped.append(idx)
            continue

        opportunity = report.feature_opportunities[idx]

        # Create idea
        idea = Idea(
            product_id=product_id,
            title=f"Add: {opportunity.get('feature_name', 'Unknown Feature')}",
            what_description=opportunity.get('summary', ''),
            why_description=opportunity.get('user_value', ''),
            use_case_description=opportunity.get('market_context', ''),
            status=IdeaStatus.PENDING,
            source_type=SourceType.COMPETITOR_AUTOMATED,
            source_metadata={
                'source': 'landscape_synthesis',
                'opportunity_index': idx,
                'feature_name': opportunity.get('feature_name'),
                'priority_score': opportunity.get('priority_score'),
                'competitors_with_feature': opportunity.get('competitors_with_feature', [])
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
            message=f"Idea created for opportunity: {opportunity.get('feature_name', 'Unknown')}"
        ))

    db.commit()

    # Queue triage tasks
    for resp in results:
        send_task('triage_idea_task', resp.job_id)

    # Add note about skipped opportunities to last result
    if skipped and results:
        results[-1].message += f" (Skipped {len(skipped)} opportunity/ies with existing ideas)"
    elif skipped and not results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"All selected opportunities already have ideas created. Skipped indices: {skipped}"
        )

    return results


class ExportOpportunitiesRequest(BaseModel):
    """Request to export selected feature opportunities as JSON."""
    opportunity_indices: List[int] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Indices of feature opportunities to export (0-indexed)"
    )


@router.post("/{product_id}/landscape-report/export-json")
def export_opportunities_json(
    product_id: int,
    request: ExportOpportunitiesRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Export selected feature opportunities as JSON.

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

    # Get the landscape report
    report = db.query(LandscapeOpportunityReport).filter(
        LandscapeOpportunityReport.product_id == product_id
    ).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No landscape report found. Run landscape synthesis first."
        )

    if not report.feature_opportunities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No feature opportunities in the landscape report."
        )

    # Validate indices
    max_index = len(report.feature_opportunities) - 1
    invalid_indices = [i for i in request.opportunity_indices if i < 0 or i > max_index]
    if invalid_indices:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid opportunity indices: {invalid_indices}. Valid range: 0-{max_index}"
        )

    # Build export data for selected opportunities
    selected_opportunities = [
        report.feature_opportunities[idx]
        for idx in request.opportunity_indices
    ]

    export_data = {
        "version": "1.0",
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        "product_id": product_id,
        "product_name": product.product_name,
        "feature_ideas": selected_opportunities,
        "metadata": {
            "total_opportunities_in_report": len(report.feature_opportunities),
            "exported_count": len(selected_opportunities),
            "report_version": report.report_version,
            "source_report_ids": report.source_competitor_report_ids,
        }
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f"attachment; filename=feature_opportunities_v{report.report_version}.json"
        }
    )


@router.get("/{product_id}/landscape-report/opportunity/{opp_index}/idea-status")
def get_opportunity_idea_status(
    product_id: int,
    opp_index: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Check if an idea has been created from a specific landscape opportunity.

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
        if (metadata.get('source') == 'landscape_synthesis' and
            str(metadata.get('opportunity_index')) == str(opp_index)):
            existing_idea = idea
            break

    return {
        'idea_created': existing_idea is not None,
        'idea_id': existing_idea.id if existing_idea else None
    }


@router.get("/{product_id}/landscape-report/idea-statuses")
def get_all_opportunity_idea_statuses(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get idea status for all opportunities in the landscape report.

    Returns a dictionary mapping opportunity indices to their idea status.
    Useful for batch loading the UI with idea badges.
    """
    verify_product_access(db, product_id, current_user)

    # Get all landscape synthesis ideas for this product
    # Filter in Python since SQLite doesn't support JSON path operators
    all_ideas = db.query(Idea).filter(
        Idea.product_id == product_id,
        Idea.source_type == SourceType.COMPETITOR_AUTOMATED
    ).all()

    # Build status map
    status_map = {}
    for idea in all_ideas:
        metadata = idea.source_metadata or {}
        if metadata.get('source') == 'landscape_synthesis':
            opp_idx = metadata.get('opportunity_index')
            if opp_idx is not None:
                status_map[opp_idx] = {
                    'idea_created': True,
                    'idea_id': idea.id
                }

    return {
        'statuses': status_map,
        'total_ideas_created': len(status_map)
    }


@router.get("/{product_id}/landscape-report/export")
def export_landscape_report(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Export the landscape report as markdown."""
    from fastapi.responses import PlainTextResponse

    verify_product_access(db, product_id, current_user)

    report = db.query(LandscapeOpportunityReport).filter(
        LandscapeOpportunityReport.product_id == product_id
    ).first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No landscape report found for this product"
        )

    return PlainTextResponse(
        content=report.report_content_md or "# No report content available",
        media_type="text/markdown",
        headers={
            "Content-Disposition": f"attachment; filename=landscape_synthesis_v{report.report_version}.md"
        }
    )
