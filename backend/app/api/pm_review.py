"""
PM Review Queue API endpoints for Phase 4.

This module provides REST API endpoints for:
- Viewing and filtering the PM review queue
- Taking actions on queue items (approve, reject, defer)
- Managing assignments
- Queue statistics
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
    PMReviewQueue,
    ReviewQueueType,
    ReviewQueueStatus,
    ReviewQueuePriority,
    AlertType
)
from app.api.deps import verify_product_access
from app.models.competitor_intelligence import ProductPermissionLevel
from app.services.pm_review_service import PMReviewService


router = APIRouter(prefix="/pm-review", tags=["PM Review"])


# =============================================================================
# Request/Response Schemas
# =============================================================================

class QueueItemResponse(BaseModel):
    """Response schema for a queue item."""
    id: int
    queue_type: str
    status: str
    priority: str
    item_type: str
    item_id: int
    title: str
    summary: Optional[str]
    alert_type: Optional[str]
    alert_severity: Optional[str]
    metadata: Optional[dict]
    product_id: int
    assigned_to_user_id: Optional[int]
    reviewed_by_user_id: Optional[int]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    review_action: Optional[str]
    created_at: datetime
    due_by: Optional[datetime]


class QueueListResponse(BaseModel):
    """Response schema for queue listing."""
    items: List[QueueItemResponse]
    total: int
    limit: int
    offset: int


class QueueStatsResponse(BaseModel):
    """Response schema for queue statistics."""
    product_id: int
    total_pending: int
    total_in_review: int
    total_approved: int
    total_rejected: int
    by_type: dict
    by_priority: dict


class ReviewActionRequest(BaseModel):
    """Request schema for review actions."""
    notes: Optional[str] = Field(None, description="Review notes")


class ApproveRequest(ReviewActionRequest):
    """Request schema for approving an item."""
    publish_idea: bool = Field(True, description="For ideas: publish for voting")


class RejectRequest(ReviewActionRequest):
    """Request schema for rejecting an item."""
    reason: Optional[str] = Field(None, description="Reason for rejection")


class DeferRequest(ReviewActionRequest):
    """Request schema for deferring an item."""
    defer_until: Optional[datetime] = Field(None, description="Date to resurface the item")


class AssignRequest(BaseModel):
    """Request schema for assigning an item."""
    assigned_to_user_id: int = Field(..., description="User ID to assign to")


# =============================================================================
# Helper Functions
# =============================================================================

def queue_item_to_response(item: PMReviewQueue) -> QueueItemResponse:
    """Convert queue item to response schema."""
    return QueueItemResponse(
        id=item.id,
        queue_type=item.queue_type.value,
        status=item.status.value,
        priority=item.priority.value,
        item_type=item.item_type,
        item_id=item.item_id,
        title=item.title,
        summary=item.summary,
        alert_type=item.alert_type.value if item.alert_type else None,
        alert_severity=item.alert_severity,
        metadata=item.item_metadata,
        product_id=item.product_id,
        assigned_to_user_id=item.assigned_to_user_id,
        reviewed_by_user_id=item.reviewed_by_user_id,
        reviewed_at=item.reviewed_at,
        review_notes=item.review_notes,
        review_action=item.review_action,
        created_at=item.created_at,
        due_by=item.due_by,
    )


# =============================================================================
# Queue Listing Endpoints
# =============================================================================

@router.get("/queue", response_model=QueueListResponse)
def get_review_queue(
    product_id: Optional[int] = Query(None, description="Product ID (optional - omit for all products)"),
    queue_type: Optional[str] = Query(None, description="Filter by type: idea, competitive_alert, report"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    assigned_to_me: bool = Query(False, description="Only show items assigned to current user"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order_by: str = Query("priority_created", description="Sort: priority_created, created_at, due_by"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get PM review queue items with filtering.

    Returns items needing review. When product_id is provided, requires EDIT
    permission on that product. When omitted, returns items for all products
    the user has EDIT access to.
    """
    # Check permission if specific product requested
    if product_id:
        verify_product_access(db, product_id, current_user, ProductPermissionLevel.EDIT)

    service = PMReviewService(db)

    # Parse enum filters
    queue_type_enum = None
    if queue_type:
        try:
            queue_type_enum = ReviewQueueType(queue_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid queue_type: {queue_type}"
            )

    status_enum = None
    if status_filter:
        try:
            status_enum = ReviewQueueStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )

    priority_enum = None
    if priority:
        try:
            priority_enum = ReviewQueuePriority(priority)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid priority: {priority}"
            )

    # Get assigned_to filter
    assigned_to_user_id = current_user.id if assigned_to_me else None

    # Get items
    items, total = service.get_queue_items(
        product_id=product_id,
        queue_type=queue_type_enum,
        status=status_enum,
        priority=priority_enum,
        assigned_to_user_id=assigned_to_user_id,
        limit=limit,
        offset=offset,
        order_by=order_by,
    )

    return QueueListResponse(
        items=[queue_item_to_response(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/queue/{item_id}", response_model=QueueItemResponse)
def get_queue_item(
    item_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a single queue item by ID.

    Requires EDIT permission on the product.
    """
    service = PMReviewService(db)
    item = service.get_queue_item(item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue item {item_id} not found"
        )

    # Check permission
    verify_product_access(db, item.product_id, current_user, ProductPermissionLevel.EDIT)

    return queue_item_to_response(item)


@router.get("/stats/{product_id}", response_model=QueueStatsResponse)
def get_queue_stats(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get queue statistics for a product.

    Returns counts by type, status, and priority.
    Requires VIEW permission on the product.
    """
    # Check permission
    verify_product_access(db, product_id, current_user, ProductPermissionLevel.VIEW)

    service = PMReviewService(db)
    stats = service.get_queue_stats(product_id)

    return QueueStatsResponse(**stats)


# =============================================================================
# Queue Action Endpoints
# =============================================================================

@router.post("/queue/{item_id}/assign", response_model=QueueItemResponse)
def assign_queue_item(
    item_id: int,
    request: AssignRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Assign a queue item to a user.

    Requires EDIT permission on the product.
    """
    service = PMReviewService(db)
    item = service.get_queue_item(item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue item {item_id} not found"
        )

    # Check permission
    verify_product_access(db, item.product_id, current_user, ProductPermissionLevel.EDIT)

    try:
        updated = service.assign_item(item_id, request.assigned_to_user_id)
        return queue_item_to_response(updated)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/queue/{item_id}/start-review", response_model=QueueItemResponse)
def start_review(
    item_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Start reviewing a queue item (self-assign and mark as in-review).

    Requires EDIT permission on the product.
    """
    service = PMReviewService(db)
    item = service.get_queue_item(item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue item {item_id} not found"
        )

    # Check permission
    verify_product_access(db, item.product_id, current_user, ProductPermissionLevel.EDIT)

    try:
        updated = service.start_review(item_id, current_user.id)
        return queue_item_to_response(updated)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/queue/{item_id}/approve", response_model=QueueItemResponse)
def approve_queue_item(
    item_id: int,
    request: ApproveRequest = ApproveRequest(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Approve a queue item.

    For ideas: Updates triage status and optionally publishes for voting.
    Requires EDIT permission on the product.
    """
    service = PMReviewService(db)
    item = service.get_queue_item(item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue item {item_id} not found"
        )

    # Check permission
    verify_product_access(db, item.product_id, current_user, ProductPermissionLevel.EDIT)

    try:
        updated = service.approve_item(
            item_id,
            current_user.id,
            notes=request.notes,
            publish_idea=request.publish_idea
        )
        return queue_item_to_response(updated)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/queue/{item_id}/reject", response_model=QueueItemResponse)
def reject_queue_item(
    item_id: int,
    request: RejectRequest = RejectRequest(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Reject a queue item.

    For ideas: Updates triage status to rejected.
    For alerts: Dismisses the alert.
    Requires EDIT permission on the product.
    """
    service = PMReviewService(db)
    item = service.get_queue_item(item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue item {item_id} not found"
        )

    # Check permission
    verify_product_access(db, item.product_id, current_user, ProductPermissionLevel.EDIT)

    try:
        updated = service.reject_item(
            item_id,
            current_user.id,
            notes=request.notes,
            reason=request.reason
        )
        return queue_item_to_response(updated)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/queue/{item_id}/defer", response_model=QueueItemResponse)
def defer_queue_item(
    item_id: int,
    request: DeferRequest = DeferRequest(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Defer a queue item for later review.

    Requires EDIT permission on the product.
    """
    service = PMReviewService(db)
    item = service.get_queue_item(item_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue item {item_id} not found"
        )

    # Check permission
    verify_product_access(db, item.product_id, current_user, ProductPermissionLevel.EDIT)

    try:
        updated = service.defer_item(
            item_id,
            current_user.id,
            defer_until=request.defer_until,
            notes=request.notes
        )
        return queue_item_to_response(updated)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# =============================================================================
# Batch Operations
# =============================================================================

class BatchActionRequest(BaseModel):
    """Request schema for batch actions."""
    item_ids: List[int] = Field(..., description="List of queue item IDs")
    notes: Optional[str] = Field(None, description="Notes to apply to all items")


class BatchActionResponse(BaseModel):
    """Response schema for batch actions."""
    success_count: int
    failed_count: int
    errors: List[dict]


@router.post("/queue/batch/approve", response_model=BatchActionResponse)
def batch_approve(
    request: BatchActionRequest,
    publish_ideas: bool = Query(True, description="Publish approved ideas for voting"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Approve multiple queue items at once.

    Requires EDIT permission on all items' products.
    """
    service = PMReviewService(db)
    success_count = 0
    failed_count = 0
    errors = []

    for item_id in request.item_ids:
        try:
            item = service.get_queue_item(item_id)
            if not item:
                errors.append({"item_id": item_id, "error": "Not found"})
                failed_count += 1
                continue

            # Check permission
            verify_product_access(db, item.product_id, current_user, ProductPermissionLevel.EDIT)

            service.approve_item(
                item_id,
                current_user.id,
                notes=request.notes,
                publish_idea=publish_ideas
            )
            success_count += 1

        except HTTPException as e:
            errors.append({"item_id": item_id, "error": e.detail})
            failed_count += 1
        except Exception as e:
            errors.append({"item_id": item_id, "error": str(e)})
            failed_count += 1

    return BatchActionResponse(
        success_count=success_count,
        failed_count=failed_count,
        errors=errors,
    )


@router.post("/queue/batch/reject", response_model=BatchActionResponse)
def batch_reject(
    request: BatchActionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Reject multiple queue items at once.

    Requires EDIT permission on all items' products.
    """
    service = PMReviewService(db)
    success_count = 0
    failed_count = 0
    errors = []

    for item_id in request.item_ids:
        try:
            item = service.get_queue_item(item_id)
            if not item:
                errors.append({"item_id": item_id, "error": "Not found"})
                failed_count += 1
                continue

            # Check permission
            verify_product_access(db, item.product_id, current_user, ProductPermissionLevel.EDIT)

            service.reject_item(
                item_id,
                current_user.id,
                notes=request.notes
            )
            success_count += 1

        except HTTPException as e:
            errors.append({"item_id": item_id, "error": e.detail})
            failed_count += 1
        except Exception as e:
            errors.append({"item_id": item_id, "error": str(e)})
            failed_count += 1

    return BatchActionResponse(
        success_count=success_count,
        failed_count=failed_count,
        errors=errors,
    )
