"""PM Review tools for MCP server."""

from mcp_server import mcp
from mcp_server.db import get_session
from mcp_server.permissions import require_product_access
from mcp_server.user_context import get_mcp_user_id

from app.models.competitor_intelligence import ProductPermissionLevel


@mcp.tool()
def review_action(item_id: int, item_type: str, action: str, notes: str = "") -> dict:
    """Take a review action on an idea or PM review queue item.

    Args:
        item_id: The ID of the item to review (idea ID or queue item ID).
        item_type: "idea" for direct idea review, or "queue_item" for PM review queue items.
        action: "approve", "reject", or "defer".
        notes: Optional review notes explaining the decision.
    """
    valid_types = {"idea", "queue_item"}
    if item_type not in valid_types:
        return {"error": f"Invalid item_type '{item_type}'. Must be one of: {sorted(valid_types)}"}

    valid_actions = {"approve", "reject", "defer"}
    if action not in valid_actions:
        return {"error": f"Invalid action '{action}'. Must be one of: {sorted(valid_actions)}"}

    with get_session() as db:
        if item_type == "idea":
            return _review_idea(db, item_id, action, notes)
        else:
            return _review_queue_item(db, item_id, action, notes)


def _review_idea(db, idea_id: int, action: str, notes: str) -> dict:
    """Review an idea directly (approve/reject/defer)."""
    from app.models.idea import Idea, IdeaStatus
    from app.models.idea_status_history import IdeaStatusHistory

    idea = db.query(Idea).get(idea_id)
    if not idea:
        return {"error": f"Idea {idea_id} not found"}

    denied = require_product_access(db, idea.product_id, ProductPermissionLevel.EDIT)
    if denied:
        return denied

    old_status = idea.status

    if action == "approve":
        idea.status = IdeaStatus.ACCEPTED
        idea.is_active = True
    elif action == "reject":
        idea.status = IdeaStatus.NOT_APPROPRIATE
        idea.is_active = False
    elif action == "defer":
        idea.status = IdeaStatus.NEEDS_REVIEW
        # Keep current is_active state for deferred items

    # Record status change
    history = IdeaStatusHistory(
        idea_id=idea.id,
        previous_status=old_status,
        new_status=idea.status,
        change_source="mcp_review",
        comment=notes or None,
    )
    db.add(history)
    db.flush()

    return {
        "item_type": "idea",
        "idea_id": idea.id,
        "title": idea.title,
        "action": action,
        "old_status": old_status.value if old_status else None,
        "new_status": idea.status.value,
        "is_active": idea.is_active,
        "notes": notes or None,
    }


def _review_queue_item(db, item_id: int, action: str, notes: str) -> dict:
    """Review a PM review queue item using the PMReviewService."""
    from app.models.pm_review import PMReviewQueue
    from app.services.pm_review_service import PMReviewService

    item = db.query(PMReviewQueue).get(item_id)
    if not item:
        return {"error": f"Queue item {item_id} not found"}

    denied = require_product_access(db, item.product_id, ProductPermissionLevel.EDIT)
    if denied:
        return denied

    reviewer_id = get_mcp_user_id()
    service = PMReviewService(db)

    try:
        if action == "approve":
            item = service.approve_item(item_id, reviewer_id, notes=notes or None)
        elif action == "reject":
            item = service.reject_item(item_id, reviewer_id, notes=notes or None)
        elif action == "defer":
            item = service.defer_item(item_id, reviewer_id, notes=notes or None)
    except ValueError as e:
        return {"error": str(e)}

    return {
        "item_type": "queue_item",
        "queue_item_id": item.id,
        "queue_type": item.queue_type.value if item.queue_type else None,
        "title": item.title,
        "action": action,
        "status": item.status.value if item.status else None,
        "notes": notes or None,
    }


@mcp.tool()
def review_get_queue(
    product_id: int,
    queue_type: str = "",
    status_filter: str = "",
    limit: int = 20,
) -> dict:
    """List items in the PM review queue with optional filters.

    Args:
        product_id: The product to get the review queue for.
        queue_type: Filter by type: "idea", "alert", "report". Leave empty for all.
        status_filter: Filter by status: "pending", "in_review", "approved", "rejected", "deferred". Leave empty for all.
        limit: Maximum number of items to return (default 20).
    """
    from app.models.pm_review import ReviewQueueType, ReviewQueueStatus
    from app.services.pm_review_service import PMReviewService

    with get_session() as db:
        denied = require_product_access(db, product_id, ProductPermissionLevel.EDIT)
        if denied:
            return denied

        # Parse optional filters
        qt = None
        if queue_type:
            try:
                qt = ReviewQueueType(queue_type)
            except ValueError:
                valid = [e.value for e in ReviewQueueType]
                return {"error": f"Invalid queue_type '{queue_type}'. Must be one of: {valid}"}

        sf = None
        if status_filter:
            try:
                sf = ReviewQueueStatus(status_filter)
            except ValueError:
                valid = [e.value for e in ReviewQueueStatus]
                return {"error": f"Invalid status_filter '{status_filter}'. Must be one of: {valid}"}

        service = PMReviewService(db)
        items, total = service.get_queue_items(
            product_id=product_id,
            queue_type=qt,
            status=sf,
            limit=limit,
        )

        return {
            "product_id": product_id,
            "total": total,
            "items": [
                {
                    "queue_item_id": item.id,
                    "queue_type": item.queue_type.value if item.queue_type else None,
                    "status": item.status.value if item.status else None,
                    "priority": item.priority.value if item.priority else None,
                    "title": item.title,
                    "summary": item.summary,
                    "source_id": item.source_id,
                    "source_type": item.source_type,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                    "due_by": item.due_by.isoformat() if item.due_by else None,
                }
                for item in items
            ],
        }


@mcp.tool()
def review_get_stats(product_id: int) -> dict:
    """Get PM review queue statistics — counts by status, type, and priority.

    Args:
        product_id: The product to get review stats for.
    """
    from app.services.pm_review_service import PMReviewService

    with get_session() as db:
        denied = require_product_access(db, product_id)
        if denied:
            return denied

        service = PMReviewService(db)
        stats = service.get_queue_stats(product_id)

        # Convert enum keys to string values for JSON serialization
        serializable_stats = {"product_id": product_id}
        for key, value in stats.items():
            if key == "product_id":
                continue
            if isinstance(value, dict):
                serializable_stats[key] = {
                    (k.value if hasattr(k, 'value') else str(k)): v
                    for k, v in value.items()
                }
            else:
                serializable_stats[key] = value

        return serializable_stats
