"""
Monitoring Configuration API endpoints for Phase 4.

This module provides REST API endpoints for:
- Configuring competitive monitoring per product
- Viewing monitoring status and history
- Triggering manual monitoring runs
- Managing competitor snapshots
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.utils.security import get_current_active_user, get_product_owner_or_admin
from app.models.user import User
from app.models.pm_review import (
    MonitoringConfig,
    CompetitorSnapshot,
    AlertType
)
from app.models.competitor_intelligence import ProductPermissionLevel, ProductCompetitor
from app.services.pm_review_service import PMReviewService
from app.services.permission_service import PermissionService


router = APIRouter(prefix="/monitoring", tags=["Competitive Monitoring"])


# =============================================================================
# Request/Response Schemas
# =============================================================================

class MonitoringConfigResponse(BaseModel):
    """Response schema for monitoring configuration."""
    id: int
    product_id: int
    monitoring_enabled: bool
    monitoring_frequency: str
    last_monitored_at: Optional[datetime]
    next_scheduled_at: Optional[datetime]
    alert_on_new_features: bool
    alert_on_removed_features: bool
    alert_on_new_competitors: bool
    min_feature_change_threshold: int
    auto_generate_ideas: bool
    auto_idea_confidence_threshold: float
    notify_product_owners: bool
    notification_settings: Optional[dict]
    created_at: datetime
    updated_at: datetime


class MonitoringConfigRequest(BaseModel):
    """Request schema for updating monitoring configuration."""
    monitoring_enabled: bool = Field(False, description="Enable/disable monitoring")
    monitoring_frequency: str = Field("weekly", description="Frequency: daily, weekly, biweekly, monthly")
    alert_on_new_features: bool = Field(True, description="Alert when competitors add features")
    alert_on_removed_features: bool = Field(True, description="Alert when competitors remove features")
    alert_on_new_competitors: bool = Field(True, description="Alert on new competitors")
    min_feature_change_threshold: int = Field(1, ge=1, description="Min features changed to alert")
    auto_generate_ideas: bool = Field(False, description="Auto-generate ideas from features")
    auto_idea_confidence_threshold: float = Field(0.8, ge=0, le=1, description="Confidence threshold for auto ideas")
    notify_product_owners: bool = Field(True, description="Notify product owners of changes")
    notification_settings: Optional[dict] = Field(None, description="Notification channel settings")


class SnapshotResponse(BaseModel):
    """Response schema for a competitor snapshot."""
    id: int
    product_competitor_id: int
    competitor_name: str
    competitor_url: Optional[str]
    snapshot_date: datetime
    feature_count: int
    has_changes: bool
    change_summary: Optional[str]
    changes_detected: Optional[dict]
    alert_generated: bool
    alert_type: Optional[str]
    previous_snapshot_id: Optional[int]
    created_at: datetime


class SnapshotListResponse(BaseModel):
    """Response schema for snapshot listing."""
    snapshots: List[SnapshotResponse]
    total: int


class MonitoringTriggerResponse(BaseModel):
    """Response for triggering monitoring."""
    job_uuid: str
    status: str
    message: str


# =============================================================================
# Helper Functions
# =============================================================================

def check_product_permission(
    db: Session,
    user: User,
    product_id: int,
    required_level: ProductPermissionLevel = ProductPermissionLevel.EDIT
):
    """Check user has permission for product."""
    from app.models.competitor_intelligence import CIProduct

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
            detail=f"User does not have {required_level.value} permission for product {product_id}"
        )

    return product


# =============================================================================
# Monitoring Configuration Endpoints
# =============================================================================

@router.get("/config/{product_id}", response_model=MonitoringConfigResponse)
def get_monitoring_config(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get monitoring configuration for a product.

    Returns the current monitoring settings. If no config exists,
    creates a default one.
    """
    # Check permission
    check_product_permission(db, current_user, product_id, ProductPermissionLevel.VIEW)

    service = PMReviewService(db)
    config = service.get_monitoring_config(product_id)

    if not config:
        # Create default config
        config = service.create_or_update_monitoring_config(
            product_id=product_id,
            enabled=False,
            frequency="weekly"
        )

    return MonitoringConfigResponse(
        id=config.id,
        product_id=config.product_id,
        monitoring_enabled=config.monitoring_enabled,
        monitoring_frequency=config.monitoring_frequency,
        last_monitored_at=config.last_monitored_at,
        next_scheduled_at=config.next_scheduled_at,
        alert_on_new_features=config.alert_on_new_features,
        alert_on_removed_features=config.alert_on_removed_features,
        alert_on_new_competitors=config.alert_on_new_competitors,
        min_feature_change_threshold=config.min_feature_change_threshold,
        auto_generate_ideas=config.auto_generate_ideas,
        auto_idea_confidence_threshold=config.auto_idea_confidence_threshold,
        notify_product_owners=config.notify_product_owners,
        notification_settings=config.notification_settings,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.put("/config/{product_id}", response_model=MonitoringConfigResponse)
def update_monitoring_config(
    product_id: int,
    request: MonitoringConfigRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update monitoring configuration for a product.

    Requires EDIT permission on the product.
    """
    # Check permission
    check_product_permission(db, current_user, product_id, ProductPermissionLevel.EDIT)

    # Validate frequency
    valid_frequencies = ["daily", "weekly", "biweekly", "monthly"]
    if request.monitoring_frequency not in valid_frequencies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid frequency. Must be one of: {valid_frequencies}"
        )

    service = PMReviewService(db)
    config = service.create_or_update_monitoring_config(
        product_id=product_id,
        enabled=request.monitoring_enabled,
        frequency=request.monitoring_frequency,
        alert_on_new_features=request.alert_on_new_features,
        alert_on_removed_features=request.alert_on_removed_features,
        alert_on_new_competitors=request.alert_on_new_competitors,
        min_feature_change_threshold=request.min_feature_change_threshold,
        auto_generate_ideas=request.auto_generate_ideas,
        auto_idea_confidence_threshold=request.auto_idea_confidence_threshold,
        notify_product_owners=request.notify_product_owners,
        notification_settings=request.notification_settings,
    )

    return MonitoringConfigResponse(
        id=config.id,
        product_id=config.product_id,
        monitoring_enabled=config.monitoring_enabled,
        monitoring_frequency=config.monitoring_frequency,
        last_monitored_at=config.last_monitored_at,
        next_scheduled_at=config.next_scheduled_at,
        alert_on_new_features=config.alert_on_new_features,
        alert_on_removed_features=config.alert_on_removed_features,
        alert_on_new_competitors=config.alert_on_new_competitors,
        min_feature_change_threshold=config.min_feature_change_threshold,
        auto_generate_ideas=config.auto_generate_ideas,
        auto_idea_confidence_threshold=config.auto_idea_confidence_threshold,
        notify_product_owners=config.notify_product_owners,
        notification_settings=config.notification_settings,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.post("/config/{product_id}/enable", response_model=MonitoringConfigResponse)
def enable_monitoring(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Enable monitoring for a product.

    Quick endpoint to turn on monitoring with default settings.
    """
    check_product_permission(db, current_user, product_id, ProductPermissionLevel.EDIT)

    service = PMReviewService(db)
    config = service.get_monitoring_config(product_id)

    if config:
        config.monitoring_enabled = True
        db.commit()
        db.refresh(config)
    else:
        config = service.create_or_update_monitoring_config(
            product_id=product_id,
            enabled=True,
            frequency="weekly"
        )

    return MonitoringConfigResponse(
        id=config.id,
        product_id=config.product_id,
        monitoring_enabled=config.monitoring_enabled,
        monitoring_frequency=config.monitoring_frequency,
        last_monitored_at=config.last_monitored_at,
        next_scheduled_at=config.next_scheduled_at,
        alert_on_new_features=config.alert_on_new_features,
        alert_on_removed_features=config.alert_on_removed_features,
        alert_on_new_competitors=config.alert_on_new_competitors,
        min_feature_change_threshold=config.min_feature_change_threshold,
        auto_generate_ideas=config.auto_generate_ideas,
        auto_idea_confidence_threshold=config.auto_idea_confidence_threshold,
        notify_product_owners=config.notify_product_owners,
        notification_settings=config.notification_settings,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.post("/config/{product_id}/disable", response_model=MonitoringConfigResponse)
def disable_monitoring(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Disable monitoring for a product.
    """
    check_product_permission(db, current_user, product_id, ProductPermissionLevel.EDIT)

    service = PMReviewService(db)
    config = service.get_monitoring_config(product_id)

    if config:
        config.monitoring_enabled = False
        db.commit()
        db.refresh(config)
    else:
        config = service.create_or_update_monitoring_config(
            product_id=product_id,
            enabled=False,
            frequency="weekly"
        )

    return MonitoringConfigResponse(
        id=config.id,
        product_id=config.product_id,
        monitoring_enabled=config.monitoring_enabled,
        monitoring_frequency=config.monitoring_frequency,
        last_monitored_at=config.last_monitored_at,
        next_scheduled_at=config.next_scheduled_at,
        alert_on_new_features=config.alert_on_new_features,
        alert_on_removed_features=config.alert_on_removed_features,
        alert_on_new_competitors=config.alert_on_new_competitors,
        min_feature_change_threshold=config.min_feature_change_threshold,
        auto_generate_ideas=config.auto_generate_ideas,
        auto_idea_confidence_threshold=config.auto_idea_confidence_threshold,
        notify_product_owners=config.notify_product_owners,
        notification_settings=config.notification_settings,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


# =============================================================================
# Snapshot Endpoints
# =============================================================================

@router.get("/snapshots/{product_id}", response_model=SnapshotListResponse)
def get_snapshots(
    product_id: int,
    competitor_id: Optional[int] = Query(None, description="Filter by competitor ID"),
    has_changes: Optional[bool] = Query(None, description="Filter by whether changes were detected"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get competitor snapshots for a product.

    Returns historical snapshots showing competitive changes over time.
    """
    check_product_permission(db, current_user, product_id, ProductPermissionLevel.VIEW)

    # Build query joining with ProductCompetitor
    query = db.query(CompetitorSnapshot).join(
        ProductCompetitor,
        CompetitorSnapshot.product_competitor_id == ProductCompetitor.id
    ).filter(
        ProductCompetitor.product_id == product_id
    )

    if competitor_id:
        query = query.filter(CompetitorSnapshot.product_competitor_id == competitor_id)
    if has_changes is not None:
        query = query.filter(CompetitorSnapshot.has_changes == has_changes)

    total = query.count()
    snapshots = query.order_by(CompetitorSnapshot.snapshot_date.desc()).offset(offset).limit(limit).all()

    # Get competitor info for response
    snapshot_responses = []
    for snapshot in snapshots:
        competitor = db.query(ProductCompetitor).get(snapshot.product_competitor_id)
        snapshot_responses.append(SnapshotResponse(
            id=snapshot.id,
            product_competitor_id=snapshot.product_competitor_id,
            competitor_name=competitor.competitor_name if competitor else "Unknown",
            competitor_url=competitor.competitor_url if competitor else None,
            snapshot_date=snapshot.snapshot_date,
            feature_count=snapshot.feature_count,
            has_changes=snapshot.has_changes,
            change_summary=snapshot.change_summary,
            changes_detected=snapshot.changes_detected,
            alert_generated=snapshot.alert_generated,
            alert_type=snapshot.alert_type.value if snapshot.alert_type else None,
            previous_snapshot_id=snapshot.previous_snapshot_id,
            created_at=snapshot.created_at,
        ))

    return SnapshotListResponse(
        snapshots=snapshot_responses,
        total=total,
    )


@router.get("/snapshots/{product_id}/{snapshot_id}", response_model=SnapshotResponse)
def get_snapshot(
    product_id: int,
    snapshot_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a single snapshot by ID.
    """
    check_product_permission(db, current_user, product_id, ProductPermissionLevel.VIEW)

    snapshot = db.query(CompetitorSnapshot).get(snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    competitor = db.query(ProductCompetitor).get(snapshot.product_competitor_id)
    if not competitor or competitor.product_id != product_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found for this product"
        )

    return SnapshotResponse(
        id=snapshot.id,
        product_competitor_id=snapshot.product_competitor_id,
        competitor_name=competitor.competitor_name,
        competitor_url=competitor.competitor_url,
        snapshot_date=snapshot.snapshot_date,
        feature_count=snapshot.feature_count,
        has_changes=snapshot.has_changes,
        change_summary=snapshot.change_summary,
        changes_detected=snapshot.changes_detected,
        alert_generated=snapshot.alert_generated,
        alert_type=snapshot.alert_type.value if snapshot.alert_type else None,
        previous_snapshot_id=snapshot.previous_snapshot_id,
        created_at=snapshot.created_at,
    )


# =============================================================================
# Manual Monitoring Trigger
# =============================================================================

@router.post("/trigger/{product_id}", response_model=MonitoringTriggerResponse)
def trigger_monitoring(
    product_id: int,
    force_full: bool = Query(False, description="Force full analysis instead of differential"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger a monitoring run for a product.

    Queues a competitive monitoring job that will:
    - Check all tracked competitors for changes
    - Create snapshots of current state
    - Generate alerts for significant changes

    Requires EDIT permission on the product.
    """
    check_product_permission(db, current_user, product_id, ProductPermissionLevel.EDIT)

    # Import here to avoid circular imports
    from app.queue.tasks import monitor_competitors_task
    from app.models.queue import QueueJob, JobType, JobStatus

    # Create queue job
    job = QueueJob(
        job_type=JobType.COMPETITIVE_MONITORING,
        status=JobStatus.PENDING,
        product_id=product_id,
        user_id=current_user.id,
        input_data={
            "product_id": product_id,
            "force_full": force_full,
            "triggered_by": current_user.id,
        }
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Queue the Celery task
    try:
        result = monitor_competitors_task.delay(
            job_id=job.id,
            product_id=product_id,
            force_full=force_full
        )
        job.celery_task_id = result.id
        job.status = JobStatus.QUEUED
        job.queued_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        job.status = JobStatus.FAILURE
        job.error_message = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue monitoring task: {e}"
        )

    return MonitoringTriggerResponse(
        job_uuid=job.job_uuid,
        status=job.status.value,
        message=f"Monitoring job queued for product {product_id}"
    )
