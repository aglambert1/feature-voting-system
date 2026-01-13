"""
Competitive Agents API endpoints.

This module provides REST API endpoints for the agent-centric competitive
intelligence system. Replaces the session-based workflow with:
- Configuration management for CompetitiveAgentConfig
- Per-competitor deep analysis triggers
- Feature cluster and intensity endpoints
- Strategic analysis results endpoints
- Manual feature-to-idea workflow
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.queue import JobType, JobStatus
from app.models.competitor_intelligence import CIProduct, ProductCompetitor, ProductCompetitorFeature
from app.models.competitive_agent import (
    CompetitiveAgentConfig, AgentMode, FeatureCluster, FeatureClusterMember,
    CompetitorPricingAnalysis, CompetitorPositioningAnalysis,
    CompetitorChangeEvent, CompetitorMomentumAnalysis, CompetitorFinancialsAnalysis
)
from app.models.idea import Idea, IdeaStatus, SourceType
from app.services.queue_service import QueueService
from app.utils.security import get_current_active_user, get_product_owner_or_admin


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

    # Deep Analysis
    deep_analysis_mode: str
    deep_analysis_schedule: Optional[str]
    deep_analysis_last_run: Optional[datetime]

    # Strategic Analysis Toggles
    enable_pricing_analysis: bool
    enable_positioning_analysis: bool
    enable_changes_tracking: bool
    enable_momentum_analysis: bool
    enable_financials_analysis: bool

    # Intensity Settings
    intensity_similarity_threshold: float
    intensity_idea_threshold: int

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

    enable_pricing_analysis: Optional[bool] = None
    enable_positioning_analysis: Optional[bool] = None
    enable_changes_tracking: Optional[bool] = None
    enable_momentum_analysis: Optional[bool] = None
    enable_financials_analysis: Optional[bool] = None

    intensity_similarity_threshold: Optional[float] = Field(None, ge=0.5, le=0.95)
    intensity_idea_threshold: Optional[int] = Field(None, ge=2, le=10)

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


class FeatureClusterResponse(BaseModel):
    """Response schema for feature cluster."""
    id: int
    product_id: int
    cluster_name: Optional[str]
    cluster_description: Optional[str]
    competitor_count: int
    feature_count: int
    idea_generated: bool
    generated_idea_id: Optional[int]

    class Config:
        from_attributes = True


class ClusterDetailResponse(BaseModel):
    """Detailed response for a feature cluster including members."""
    id: int
    product_id: int
    cluster_name: Optional[str]
    cluster_description: Optional[str]
    competitor_count: int
    feature_count: int
    idea_generated: bool
    generated_idea_id: Optional[int]
    members: List[dict]

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
    """Verify product exists and user has access."""
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )
    # Note: Could add permission check here based on ProductPermission
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
        enable_pricing_analysis=config.enable_pricing_analysis,
        enable_positioning_analysis=config.enable_positioning_analysis,
        enable_changes_tracking=config.enable_changes_tracking,
        enable_momentum_analysis=config.enable_momentum_analysis,
        enable_financials_analysis=config.enable_financials_analysis,
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
    if request.enable_pricing_analysis is not None:
        config.enable_pricing_analysis = request.enable_pricing_analysis
    if request.enable_positioning_analysis is not None:
        config.enable_positioning_analysis = request.enable_positioning_analysis
    if request.enable_changes_tracking is not None:
        config.enable_changes_tracking = request.enable_changes_tracking
    if request.enable_momentum_analysis is not None:
        config.enable_momentum_analysis = request.enable_momentum_analysis
    if request.enable_financials_analysis is not None:
        config.enable_financials_analysis = request.enable_financials_analysis
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
# Product-Level Triggers
# ============================================================================

@router.post("/{product_id}/discover-competitors", response_model=JobResponse)
def trigger_competitor_discovery(
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
        from app.queue.tasks import discover_competitors_task
        result = discover_competitors_task.delay(job.id)
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
        from app.queue.tasks import analyze_product_task
        result = analyze_product_task.delay(job.id)
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


@router.post("/{product_id}/run-clustering", response_model=JobResponse)
def trigger_feature_clustering(
    product_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Trigger feature clustering and intensity idea generation."""
    verify_product_access(db, product_id, current_user)

    # Get config for threshold
    config = get_or_create_config(db, product_id)

    queue_service = QueueService(db)

    # Check for existing active job of this type for this product
    active_jobs = queue_service.get_active_jobs(product_id=product_id)
    existing_clustering = next(
        (j for j in active_jobs if j.job_type == JobType.FEATURE_CLUSTERING),
        None
    )
    if existing_clustering:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Feature clustering already in progress (job {existing_clustering.job_uuid})"
        )

    job = queue_service.create_job(
        job_type=JobType.FEATURE_CLUSTERING,
        input_data={
            'similarity_threshold': config.intensity_similarity_threshold,
        },
        product_id=product_id,
        user_id=current_user.id,
        auto_commit=False,  # Don't commit until Celery dispatch succeeds
    )

    # Queue the task - if this fails, rollback the job creation
    try:
        from app.queue.tasks import feature_clustering_task
        result = feature_clustering_task.delay(job.id)
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
        message=f"Feature clustering queued for product {product_id}"
    )


@router.post("/{product_id}/run-competitive-analysis", response_model=JobResponse)
def trigger_competitive_analysis(
    product_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """
    Trigger full competitive analysis workflow.

    This runs the complete analysis pipeline:
    1. Deep analysis (feature extraction + strategic analysis) for all enabled competitors
    2. Feature clustering across all extracted features
    3. Idea generation from high-intensity clusters

    Use this endpoint for the "Run Now" button on the Competitive Analysis Agent.
    Use /run-clustering if you only want to re-cluster existing features.
    """
    verify_product_access(db, product_id, current_user)

    queue_service = QueueService(db)

    # Check for existing active competitive analysis job
    active_jobs = queue_service.get_active_jobs(product_id=product_id)
    existing_analysis = next(
        (j for j in active_jobs if j.job_type in [
            JobType.SCHEDULED_DEEP_ANALYSIS,
            JobType.DEEP_ANALYSIS,
            JobType.FEATURE_CLUSTERING
        ]),
        None
    )
    if existing_analysis:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Competitive analysis already in progress (job {existing_analysis.job_uuid})"
        )

    # Check if there are competitors enabled for deep analysis
    enabled_competitors = db.query(ProductCompetitor).filter(
        ProductCompetitor.product_id == product_id,
        ProductCompetitor.status == 'active',
        ProductCompetitor.deep_analysis_enabled == True
    ).count()

    if enabled_competitors == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No competitors are enabled for deep analysis. Enable at least one competitor first."
        )

    job = queue_service.create_job(
        job_type=JobType.SCHEDULED_DEEP_ANALYSIS,
        input_data={
            'triggered_by': 'manual',
            'competitors_enabled': enabled_competitors,
        },
        product_id=product_id,
        user_id=current_user.id,
        auto_commit=False,  # Don't commit until Celery dispatch succeeds
    )

    # Queue the task - if this fails, rollback the job creation
    try:
        from app.queue.tasks import scheduled_deep_analysis_task
        result = scheduled_deep_analysis_task.delay(job.id)
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
        message=f"Competitive analysis started for {enabled_competitors} competitors"
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

    # Get feature counts
    result = []
    for comp in competitors:
        feature_count = db.query(func.count(ProductCompetitorFeature.id)).filter(
            ProductCompetitorFeature.product_competitor_id == comp.id
        ).scalar() or 0

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


# ============================================================================
# Per-Competitor Deep Analysis
# ============================================================================

@router.post("/{product_id}/competitors/{competitor_id}/deep-analysis", response_model=JobResponse)
def trigger_deep_analysis(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Trigger deep analysis for a single competitor."""
    competitor = verify_competitor_access(db, product_id, competitor_id, current_user)

    queue_service = QueueService(db)

    # Check for existing active deep analysis job for this specific competitor
    active_jobs = queue_service.get_active_jobs(product_id=product_id)
    existing_analysis = next(
        (j for j in active_jobs
         if j.job_type == JobType.DEEP_ANALYSIS
         and j.input_data.get('competitor_id') == competitor_id),
        None
    )
    if existing_analysis:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Deep analysis already in progress for this competitor (job {existing_analysis.job_uuid})"
        )

    job = queue_service.create_job(
        job_type=JobType.DEEP_ANALYSIS,
        input_data={'competitor_id': competitor_id},
        product_id=product_id,
        user_id=current_user.id,
        auto_commit=False,  # Don't commit until Celery dispatch succeeds
    )

    # Queue the task - if this fails, rollback the job creation
    try:
        from app.queue.tasks import deep_analysis_task
        result = deep_analysis_task.delay(job.id)
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
        message=f"Deep analysis queued for competitor {competitor_id}"
    )


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
    """List extracted features for a competitor."""
    verify_competitor_access(db, product_id, competitor_id, current_user)

    features = db.query(ProductCompetitorFeature).filter(
        ProductCompetitorFeature.product_competitor_id == competitor_id
    ).all()

    result = []
    for feat in features:
        # Check if feature is in a cluster
        member = db.query(FeatureClusterMember).filter(
            FeatureClusterMember.feature_id == feat.id
        ).first()

        cluster_id = None
        cluster_name = None
        if member:
            cluster = db.query(FeatureCluster).filter(
                FeatureCluster.id == member.cluster_id
            ).first()
            if cluster:
                cluster_id = cluster.id
                cluster_name = cluster.cluster_name

        result.append(FeatureResponse(
            id=feat.id,
            product_competitor_id=feat.product_competitor_id,
            feature_name=feat.feature_name,
            feature_description=feat.feature_description,
            feature_category=feat.feature_category,
            status=feat.status or 'active',
            cluster_id=cluster_id,
            cluster_name=cluster_name
        ))

    return result


@router.post("/{product_id}/competitors/{competitor_id}/features/{feature_id}/create-idea", response_model=JobResponse)
def create_idea_from_feature(
    product_id: int,
    competitor_id: int,
    feature_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Create an idea from a single competitor feature."""
    verify_competitor_access(db, product_id, competitor_id, current_user)

    # Verify feature exists
    feature = db.query(ProductCompetitorFeature).filter(
        ProductCompetitorFeature.id == feature_id,
        ProductCompetitorFeature.product_competitor_id == competitor_id
    ).first()
    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature {feature_id} not found"
        )

    # Get competitor name for context
    competitor = db.query(ProductCompetitor).filter(
        ProductCompetitor.id == competitor_id
    ).first()

    # Create idea directly
    idea = Idea(
        product_id=product_id,
        title=f"Add: {feature.feature_name}",
        what_description=feature.feature_description or f"Implement {feature.feature_name} feature",
        why_description=f"Competitor '{competitor.competitor_name}' has this feature",
        use_case_description=f"Users would benefit from {feature.feature_name}",
        status=IdeaStatus.PENDING,
        source_type=SourceType.COMPETITOR_AUTOMATED,
        source_metadata={
            'competitor_id': competitor_id,
            'competitor_name': competitor.competitor_name,
            'feature_id': feature_id,
            'feature_name': feature.feature_name
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

    from app.queue.tasks import triage_idea_task
    result = triage_idea_task.delay(job.id)
    job.celery_task_id = result.id
    db.commit()

    return JobResponse(
        job_id=job.id,
        job_uuid=job.job_uuid,
        job_type=job.job_type.value,
        status=job.status.value,
        message=f"Idea created and triage queued for feature {feature_id}"
    )


@router.post("/{product_id}/competitors/{competitor_id}/features/create-ideas", response_model=List[JobResponse])
def create_ideas_from_features(
    product_id: int,
    competitor_id: int,
    request: CreateIdeasRequest,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Create ideas from selected competitor features."""
    verify_competitor_access(db, product_id, competitor_id, current_user)

    competitor = db.query(ProductCompetitor).filter(
        ProductCompetitor.id == competitor_id
    ).first()

    results = []
    for feature_id in request.feature_ids:
        feature = db.query(ProductCompetitorFeature).filter(
            ProductCompetitorFeature.id == feature_id,
            ProductCompetitorFeature.product_competitor_id == competitor_id
        ).first()

        if not feature:
            continue

        # Create idea
        idea = Idea(
            product_id=product_id,
            title=f"Add: {feature.feature_name}",
            what_description=feature.feature_description or f"Implement {feature.feature_name} feature",
            why_description=f"Competitor '{competitor.competitor_name}' has this feature",
            use_case_description=f"Users would benefit from {feature.feature_name}",
            status=IdeaStatus.PENDING,
            source_type=SourceType.COMPETITOR_AUTOMATED,
            source_metadata={
                'competitor_id': competitor_id,
                'competitor_name': competitor.competitor_name,
                'feature_id': feature_id,
                'feature_name': feature.feature_name
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
            message=f"Idea created for feature {feature_id}"
        ))

    db.commit()

    # Queue triage tasks
    from app.queue.tasks import triage_idea_task
    for resp in results:
        triage_idea_task.delay(resp.job_id)

    return results


# ============================================================================
# Feature Clusters & Intensity
# ============================================================================

@router.get("/{product_id}/feature-clusters", response_model=List[FeatureClusterResponse])
def list_feature_clusters(
    product_id: int,
    min_competitors: Optional[int] = Query(None, description="Minimum competitor count filter"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List feature clusters with intensity scores."""
    verify_product_access(db, product_id, current_user)

    query = db.query(FeatureCluster).filter(
        FeatureCluster.product_id == product_id
    )

    if min_competitors is not None:
        query = query.filter(FeatureCluster.competitor_count >= min_competitors)

    clusters = query.order_by(FeatureCluster.competitor_count.desc()).all()

    return [FeatureClusterResponse(
        id=c.id,
        product_id=c.product_id,
        cluster_name=c.cluster_name,
        cluster_description=c.cluster_description,
        competitor_count=c.competitor_count,
        feature_count=c.feature_count,
        idea_generated=c.idea_generated,
        generated_idea_id=c.generated_idea_id
    ) for c in clusters]


@router.get("/{product_id}/feature-clusters/{cluster_id}", response_model=ClusterDetailResponse)
def get_feature_cluster(
    product_id: int,
    cluster_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get cluster details with member features."""
    verify_product_access(db, product_id, current_user)

    cluster = db.query(FeatureCluster).filter(
        FeatureCluster.id == cluster_id,
        FeatureCluster.product_id == product_id
    ).first()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found"
        )

    # Get members with feature details
    members = db.query(
        FeatureClusterMember, ProductCompetitorFeature, ProductCompetitor
    ).join(
        ProductCompetitorFeature,
        FeatureClusterMember.feature_id == ProductCompetitorFeature.id
    ).join(
        ProductCompetitor,
        ProductCompetitorFeature.product_competitor_id == ProductCompetitor.id
    ).filter(
        FeatureClusterMember.cluster_id == cluster_id
    ).all()

    member_data = []
    for member, feature, competitor in members:
        member_data.append({
            'feature_id': feature.id,
            'feature_name': feature.feature_name,
            'feature_description': feature.feature_description,
            'competitor_id': competitor.id,
            'competitor_name': competitor.competitor_name,
            'similarity_score': member.similarity_score
        })

    return ClusterDetailResponse(
        id=cluster.id,
        product_id=cluster.product_id,
        cluster_name=cluster.cluster_name,
        cluster_description=cluster.cluster_description,
        competitor_count=cluster.competitor_count,
        feature_count=cluster.feature_count,
        idea_generated=cluster.idea_generated,
        generated_idea_id=cluster.generated_idea_id,
        members=member_data
    )


@router.post("/{product_id}/feature-clusters/{cluster_id}/create-idea", response_model=JobResponse)
def create_idea_from_cluster(
    product_id: int,
    cluster_id: int,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """Manually create an idea from a feature cluster."""
    verify_product_access(db, product_id, current_user)

    cluster = db.query(FeatureCluster).filter(
        FeatureCluster.id == cluster_id,
        FeatureCluster.product_id == product_id
    ).first()

    if not cluster:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found"
        )

    if cluster.idea_generated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Idea already generated for cluster {cluster_id}"
        )

    # Queue intensity idea generation for this cluster
    queue_service = QueueService(db)
    job = queue_service.create_job(
        job_type=JobType.INTENSITY_IDEA_GENERATION,
        input_data={
            'cluster_id': cluster_id,
            'threshold': 1,  # Force generate for this specific cluster
            'chain_triage': True
        },
        product_id=product_id,
        user_id=current_user.id
    )
    db.commit()

    from app.queue.tasks import intensity_idea_generation_task
    result = intensity_idea_generation_task.delay(job.id)
    job.celery_task_id = result.id
    db.commit()

    return JobResponse(
        job_id=job.id,
        job_uuid=job.job_uuid,
        job_type=job.job_type.value,
        status=job.status.value,
        message=f"Idea generation queued for cluster {cluster_id}"
    )


# ============================================================================
# Strategic Analysis Results
# ============================================================================

@router.get("/{product_id}/competitors/{competitor_id}/pricing", response_model=Optional[PricingAnalysisResponse])
def get_pricing_analysis(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get pricing analysis for a competitor."""
    verify_competitor_access(db, product_id, competitor_id, current_user)

    analysis = db.query(CompetitorPricingAnalysis).filter(
        CompetitorPricingAnalysis.product_competitor_id == competitor_id
    ).order_by(CompetitorPricingAnalysis.analyzed_at.desc()).first()

    if not analysis:
        return None

    return PricingAnalysisResponse(
        id=analysis.id,
        product_competitor_id=analysis.product_competitor_id,
        pricing_model=analysis.pricing_model,
        has_free_tier=analysis.has_free_tier,
        has_trial=analysis.has_trial,
        trial_days=analysis.trial_days,
        pricing_tiers=analysis.pricing_tiers,
        has_enterprise=analysis.has_enterprise,
        source_url=analysis.source_url,
        confidence=analysis.confidence,
        analyzed_at=analysis.analyzed_at
    )


@router.get("/{product_id}/competitors/{competitor_id}/positioning", response_model=Optional[PositioningAnalysisResponse])
def get_positioning_analysis(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get positioning analysis for a competitor."""
    verify_competitor_access(db, product_id, competitor_id, current_user)

    analysis = db.query(CompetitorPositioningAnalysis).filter(
        CompetitorPositioningAnalysis.product_competitor_id == competitor_id
    ).order_by(CompetitorPositioningAnalysis.analyzed_at.desc()).first()

    if not analysis:
        return None

    return PositioningAnalysisResponse(
        id=analysis.id,
        product_competitor_id=analysis.product_competitor_id,
        tagline=analysis.tagline,
        value_propositions=analysis.value_propositions,
        target_audience=analysis.target_audience,
        key_differentiators=analysis.key_differentiators,
        positioning_statement=analysis.positioning_statement,
        market_segment=analysis.market_segment,
        confidence=analysis.confidence,
        analyzed_at=analysis.analyzed_at
    )


@router.get("/{product_id}/competitors/{competitor_id}/changes", response_model=List[ChangeEventResponse])
def get_change_events(
    product_id: int,
    competitor_id: int,
    limit: int = Query(20, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get recent change events for a competitor."""
    verify_competitor_access(db, product_id, competitor_id, current_user)

    events = db.query(CompetitorChangeEvent).filter(
        CompetitorChangeEvent.product_competitor_id == competitor_id
    ).order_by(CompetitorChangeEvent.detected_at.desc()).limit(limit).all()

    return [ChangeEventResponse(
        id=e.id,
        product_competitor_id=e.product_competitor_id,
        event_type=e.event_type,
        event_title=e.event_title,
        event_description=e.event_description,
        event_date=e.event_date,
        source_url=e.source_url,
        source_type=e.source_type,
        impact_level=e.impact_level,
        detected_at=e.detected_at
    ) for e in events]


@router.get("/{product_id}/competitors/{competitor_id}/momentum", response_model=Optional[MomentumAnalysisResponse])
def get_momentum_analysis(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get momentum analysis for a competitor."""
    verify_competitor_access(db, product_id, competitor_id, current_user)

    analysis = db.query(CompetitorMomentumAnalysis).filter(
        CompetitorMomentumAnalysis.product_competitor_id == competitor_id
    ).order_by(CompetitorMomentumAnalysis.analyzed_at.desc()).first()

    if not analysis:
        return None

    return MomentumAnalysisResponse(
        id=analysis.id,
        product_competitor_id=analysis.product_competitor_id,
        momentum_score=analysis.momentum_score,
        momentum_trend=analysis.momentum_trend,
        customer_growth_trend=analysis.customer_growth_trend,
        release_velocity=analysis.release_velocity,
        notable_customers=analysis.notable_customers,
        analysis_summary=analysis.analysis_summary,
        confidence=analysis.confidence,
        analyzed_at=analysis.analyzed_at
    )


@router.get("/{product_id}/competitors/{competitor_id}/financials", response_model=Optional[FinancialsAnalysisResponse])
def get_financials_analysis(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get financials analysis for a competitor."""
    verify_competitor_access(db, product_id, competitor_id, current_user)

    analysis = db.query(CompetitorFinancialsAnalysis).filter(
        CompetitorFinancialsAnalysis.product_competitor_id == competitor_id
    ).order_by(CompetitorFinancialsAnalysis.analyzed_at.desc()).first()

    if not analysis:
        return None

    return FinancialsAnalysisResponse(
        id=analysis.id,
        product_competitor_id=analysis.product_competitor_id,
        company_type=analysis.company_type,
        total_funding=analysis.total_funding,
        funding_stage=analysis.funding_stage,
        market_cap=analysis.market_cap,
        revenue_ttm=analysis.revenue_ttm,
        employee_count=analysis.employee_count,
        financial_health=analysis.financial_health,
        analysis_summary=analysis.analysis_summary,
        confidence=analysis.confidence,
        analyzed_at=analysis.analyzed_at
    )
