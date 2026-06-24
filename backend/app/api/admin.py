"""
Admin API endpoints for system management and cost tracking.

Provides admin-only endpoints for viewing LLM usage costs,
system-wide statistics, user cost summaries, and idea lifecycle
status configuration.
"""

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func as sql_func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.idea import Idea
from app.models.idea_lifecycle_status import IdeaLifecycleStatus
from app.utils.security import get_current_admin_user, get_product_owner_or_admin
from app.services.cost_tracking_service import CostTrackingService

router = APIRouter(prefix="/admin", tags=["Admin"])

MAX_LIFECYCLE_STATUSES = 3


# --- Pydantic schemas for lifecycle status endpoints ---

class LifecycleStatusCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(default="#3B82F6", pattern=r"^#[0-9A-Fa-f]{6}$")

class LifecycleStatusUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    position: Optional[int] = None
    is_active: Optional[bool] = None


def _slugify(name: str) -> str:
    """Convert a display name to a slug (lowercase, underscores)."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    return slug.strip('_')


@router.get("/costs/summary")
def get_cost_summary(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get system-wide LLM cost summary.

    Returns total costs, breakdown by operation type, by model,
    and top users by cost over the specified period.

    Admin only.
    """
    tracker = CostTrackingService(db)
    return tracker.get_system_costs(days=days)


@router.get("/costs/user/{user_id}")
def get_user_costs(
    user_id: int,
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get LLM costs for a specific user.

    Returns total cost, request count, and breakdown by operation
    over the specified period.

    Admin only.
    """
    tracker = CostTrackingService(db)
    return tracker.get_user_costs(user_id=user_id, days=days)


@router.get("/costs/product/{product_id}")
def get_product_costs(
    product_id: int,
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get LLM costs for a specific product.

    Returns total cost and breakdown by operation type
    over the specified period.

    Admin only.
    """
    tracker = CostTrackingService(db)
    return tracker.get_product_costs(product_id=product_id, days=days)


@router.get("/costs/daily-series")
def get_daily_cost_series(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Get daily cost series for trend visualization. Admin only."""
    tracker = CostTrackingService(db)
    return tracker.get_daily_cost_series(days=days)


@router.get("/costs/today")
def get_today_costs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get today's total LLM cost.

    Useful for monitoring daily spend.

    Admin only.
    """
    tracker = CostTrackingService(db)
    daily_cost = tracker.get_daily_cost()
    limit_exceeded = tracker.check_daily_limit()

    return {
        "date": "today",
        "total_cost_usd": daily_cost,
        "limit_exceeded": limit_exceeded,
        "daily_limit_usd": 50.0,  # Default limit
    }


# --- Idea Lifecycle Status CRUD ---

@router.get("/idea-lifecycle-statuses")
async def list_lifecycle_statuses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_product_owner_or_admin)
):
    """List all idea lifecycle statuses with idea counts. PO and Admin."""
    statuses = db.query(IdeaLifecycleStatus).order_by(IdeaLifecycleStatus.position).all()

    result = []
    for status in statuses:
        idea_count = db.query(sql_func.count(Idea.id)).filter(
            Idea.lifecycle_status_id == status.id
        ).scalar()
        d = status.to_dict()
        d["idea_count"] = idea_count
        result.append(d)

    return result


@router.post("/idea-lifecycle-statuses", status_code=201)
def create_lifecycle_status(
    data: LifecycleStatusCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Create a new idea lifecycle status. Max 3 total. Admin only."""
    existing_count = db.query(IdeaLifecycleStatus).count()
    if existing_count >= MAX_LIFECYCLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum of {MAX_LIFECYCLE_STATUSES} lifecycle statuses allowed"
        )

    slug = _slugify(data.name)

    # Check for duplicate name/slug
    if db.query(IdeaLifecycleStatus).filter(IdeaLifecycleStatus.slug == slug).first():
        raise HTTPException(status_code=400, detail=f"A status with a similar name already exists")

    # Set position to next available
    max_pos = db.query(sql_func.max(IdeaLifecycleStatus.position)).scalar() or 0

    status = IdeaLifecycleStatus(
        name=data.name.strip(),
        slug=slug,
        color=data.color,
        position=max_pos + 1,
        is_default=False,
        is_active=True,
    )
    db.add(status)
    db.commit()
    db.refresh(status)

    d = status.to_dict()
    d["idea_count"] = 0
    return d


@router.put("/idea-lifecycle-statuses/{status_id}")
def update_lifecycle_status(
    status_id: int,
    data: LifecycleStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update an idea lifecycle status. Admin only."""
    status = db.query(IdeaLifecycleStatus).filter(IdeaLifecycleStatus.id == status_id).first()
    if not status:
        raise HTTPException(status_code=404, detail="Lifecycle status not found")

    if data.name is not None:
        new_slug = _slugify(data.name)
        # Check for duplicate slug (excluding self)
        existing = db.query(IdeaLifecycleStatus).filter(
            IdeaLifecycleStatus.slug == new_slug,
            IdeaLifecycleStatus.id != status_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="A status with a similar name already exists")
        status.name = data.name.strip()
        status.slug = new_slug

    if data.color is not None:
        status.color = data.color

    if data.position is not None:
        status.position = data.position

    if data.is_active is not None:
        status.is_active = data.is_active

    db.commit()
    db.refresh(status)

    idea_count = db.query(sql_func.count(Idea.id)).filter(
        Idea.lifecycle_status_id == status.id
    ).scalar()
    d = status.to_dict()
    d["idea_count"] = idea_count
    return d


@router.delete("/idea-lifecycle-statuses/{status_id}")
def delete_lifecycle_status(
    status_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete an idea lifecycle status. Fails if ideas reference it. Admin only."""
    status = db.query(IdeaLifecycleStatus).filter(IdeaLifecycleStatus.id == status_id).first()
    if not status:
        raise HTTPException(status_code=404, detail="Lifecycle status not found")

    idea_count = db.query(sql_func.count(Idea.id)).filter(
        Idea.lifecycle_status_id == status.id
    ).scalar()
    if idea_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {idea_count} idea(s) still reference this status. Remove them first."
        )

    db.delete(status)
    db.commit()
    return {"message": f"Lifecycle status '{status.name}' deleted"}
