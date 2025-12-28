"""
PM Review Queue Service for Phase 4.

This service manages the unified PM review queue that consolidates:
- Ideas needing review
- Competitive alerts
- Generated reports

It provides:
- Queue item CRUD operations
- Assignment logic
- Status tracking
- Filtering and prioritization
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc

from app.models.pm_review import (
    PMReviewQueue,
    CompetitorSnapshot,
    MonitoringConfig,
    ReviewQueueType,
    ReviewQueueStatus,
    ReviewQueuePriority,
    AlertType
)
from app.models.idea import Idea, TriageStatus
from app.models.competitor_intelligence import CIProduct, ProductCompetitor


class PMReviewService:
    """
    Service for managing the PM review queue.

    Handles:
    - Adding items to the queue (ideas, alerts, reports)
    - Retrieving queue items with filtering
    - Processing review actions (approve, reject, defer)
    - Assignment to reviewers
    - Queue statistics and dashboards
    """

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Queue Item Creation
    # =========================================================================

    def add_idea_to_queue(
        self,
        idea: Idea,
        priority: ReviewQueuePriority = ReviewQueuePriority.NORMAL,
        created_by_user_id: Optional[int] = None
    ) -> PMReviewQueue:
        """
        Add an idea to the PM review queue.

        Called when an idea is triaged with NEEDS_REVIEW status.

        Args:
            idea: The idea to add to the queue
            priority: Priority level for the queue item
            created_by_user_id: ID of user who triggered this (system if None)

        Returns:
            Created PMReviewQueue item
        """
        # Check if already in queue
        existing = self.db.query(PMReviewQueue).filter(
            PMReviewQueue.item_type == "idea",
            PMReviewQueue.item_id == idea.id,
            PMReviewQueue.status == ReviewQueueStatus.PENDING
        ).first()

        if existing:
            return existing

        # Determine priority based on competitive context
        if idea.competitive_context:
            urgency = idea.competitive_context.get("competitive_urgency", "low")
            if urgency in ("high", "critical"):
                priority = ReviewQueuePriority.HIGH
            elif urgency == "medium":
                priority = ReviewQueuePriority.NORMAL

        # Build item_metadata
        item_metadata = {
            "source_type": idea.source_type.value,
            "confidence": idea.triage_confidence,
            "recommendation": idea.triage_recommendation.value if idea.triage_recommendation else None,
            "competitive_urgency": idea.competitive_context.get("competitive_urgency") if idea.competitive_context else None,
        }

        queue_item = PMReviewQueue(
            queue_type=ReviewQueueType.IDEA,
            status=ReviewQueueStatus.PENDING,
            priority=priority,
            item_type="idea",
            item_id=idea.id,
            title=f"Idea: {idea.title}",
            summary=idea.what_description[:500] if idea.what_description else None,
            item_metadata=item_metadata,
            product_id=idea.product_id,
            created_by_user_id=created_by_user_id,
            queue_job_id=idea.triage_job_id,
        )

        self.db.add(queue_item)
        self.db.commit()
        self.db.refresh(queue_item)

        return queue_item

    def add_competitive_alert(
        self,
        snapshot: CompetitorSnapshot,
        alert_type: AlertType,
        severity: str = "warning",
        created_by_user_id: Optional[int] = None
    ) -> PMReviewQueue:
        """
        Add a competitive alert to the PM review queue.

        Called when competitive monitoring detects changes.

        Args:
            snapshot: The CompetitorSnapshot that triggered the alert
            alert_type: Type of competitive change
            severity: Alert severity ("info", "warning", "critical")
            created_by_user_id: ID of user who triggered this (system if None)

        Returns:
            Created PMReviewQueue item
        """
        competitor = self.db.query(ProductCompetitor).get(snapshot.product_competitor_id)
        if not competitor:
            raise ValueError(f"Competitor not found: {snapshot.product_competitor_id}")

        # Determine priority based on severity and alert type
        if severity == "critical" or alert_type in (AlertType.MAJOR_FEATURE_LAUNCH, AlertType.NEW_COMPETITOR):
            priority = ReviewQueuePriority.URGENT
        elif severity == "warning":
            priority = ReviewQueuePriority.HIGH
        else:
            priority = ReviewQueuePriority.NORMAL

        # Build title based on alert type
        title_map = {
            AlertType.NEW_COMPETITOR: f"New Competitor: {competitor.competitor_name}",
            AlertType.COMPETITOR_REMOVED: f"Competitor Removed: {competitor.competitor_name}",
            AlertType.MAJOR_FEATURE_LAUNCH: f"New Features from {competitor.competitor_name}",
            AlertType.FEATURE_REMOVED: f"Features Removed from {competitor.competitor_name}",
            AlertType.PRICING_CHANGE: f"Pricing Change: {competitor.competitor_name}",
            AlertType.TREND_DETECTED: f"Market Trend: {competitor.competitor_name}",
        }
        title = title_map.get(alert_type, f"Alert: {competitor.competitor_name}")

        # Build item_metadata
        changes = snapshot.changes_detected or {}
        item_metadata = {
            "competitor_id": competitor.id,
            "competitor_name": competitor.competitor_name,
            "competitor_url": competitor.competitor_url,
            "new_features_count": len(changes.get("new_features", [])),
            "removed_features_count": len(changes.get("removed_features", [])),
            "modified_features_count": len(changes.get("modified_features", [])),
            "snapshot_id": snapshot.id,
        }

        queue_item = PMReviewQueue(
            queue_type=ReviewQueueType.COMPETITIVE_ALERT,
            status=ReviewQueueStatus.PENDING,
            priority=priority,
            item_type="competitor_snapshot",
            item_id=snapshot.id,
            title=title,
            summary=snapshot.change_summary,
            alert_type=alert_type,
            alert_severity=severity,
            item_metadata=item_metadata,
            product_id=competitor.product_id,
            created_by_user_id=created_by_user_id,
            queue_job_id=snapshot.queue_job_id,
        )

        self.db.add(queue_item)

        # Update snapshot with review queue reference
        snapshot.alert_generated = True
        snapshot.alert_type = alert_type
        snapshot.review_queue_id = queue_item.id

        self.db.commit()
        self.db.refresh(queue_item)

        return queue_item

    # =========================================================================
    # Queue Retrieval
    # =========================================================================

    def get_queue_items(
        self,
        product_id: Optional[int] = None,
        queue_type: Optional[ReviewQueueType] = None,
        status: Optional[ReviewQueueStatus] = None,
        assigned_to_user_id: Optional[int] = None,
        priority: Optional[ReviewQueuePriority] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "priority_created"
    ) -> Tuple[List[PMReviewQueue], int]:
        """
        Get queue items with filtering and pagination.

        Args:
            product_id: Filter by product
            queue_type: Filter by queue type (idea, alert, report)
            status: Filter by status
            assigned_to_user_id: Filter by assignee
            priority: Filter by priority
            limit: Maximum items to return
            offset: Pagination offset
            order_by: Sort order ("priority_created", "created_at", "due_by")

        Returns:
            Tuple of (list of queue items, total count)
        """
        query = self.db.query(PMReviewQueue)

        # Apply filters
        if product_id:
            query = query.filter(PMReviewQueue.product_id == product_id)
        if queue_type:
            query = query.filter(PMReviewQueue.queue_type == queue_type)
        if status:
            query = query.filter(PMReviewQueue.status == status)
        if assigned_to_user_id:
            query = query.filter(PMReviewQueue.assigned_to_user_id == assigned_to_user_id)
        if priority:
            query = query.filter(PMReviewQueue.priority == priority)

        # Get total count before pagination
        total = query.count()

        # Apply ordering
        if order_by == "priority_created":
            # Priority order: URGENT > HIGH > NORMAL > LOW
            priority_order = {
                ReviewQueuePriority.URGENT: 0,
                ReviewQueuePriority.HIGH: 1,
                ReviewQueuePriority.NORMAL: 2,
                ReviewQueuePriority.LOW: 3,
            }
            # Use case/when for priority ordering in SQL
            query = query.order_by(
                PMReviewQueue.priority,  # Enum ordering (works if defined in correct order)
                desc(PMReviewQueue.created_at)
            )
        elif order_by == "created_at":
            query = query.order_by(desc(PMReviewQueue.created_at))
        elif order_by == "due_by":
            query = query.order_by(PMReviewQueue.due_by.asc().nulls_last())

        # Apply pagination
        items = query.offset(offset).limit(limit).all()

        return items, total

    def get_queue_item(self, queue_item_id: int) -> Optional[PMReviewQueue]:
        """Get a single queue item by ID."""
        return self.db.query(PMReviewQueue).get(queue_item_id)

    def get_queue_stats(self, product_id: int) -> Dict[str, Any]:
        """
        Get queue statistics for a product.

        Returns counts by type, status, and priority.
        """
        from sqlalchemy import func

        # Count by status
        status_counts = dict(
            self.db.query(
                PMReviewQueue.status,
                func.count(PMReviewQueue.id)
            ).filter(
                PMReviewQueue.product_id == product_id
            ).group_by(PMReviewQueue.status).all()
        )

        # Count by type
        type_counts = dict(
            self.db.query(
                PMReviewQueue.queue_type,
                func.count(PMReviewQueue.id)
            ).filter(
                PMReviewQueue.product_id == product_id,
                PMReviewQueue.status == ReviewQueueStatus.PENDING
            ).group_by(PMReviewQueue.queue_type).all()
        )

        # Count by priority (pending only)
        priority_counts = dict(
            self.db.query(
                PMReviewQueue.priority,
                func.count(PMReviewQueue.id)
            ).filter(
                PMReviewQueue.product_id == product_id,
                PMReviewQueue.status == ReviewQueueStatus.PENDING
            ).group_by(PMReviewQueue.priority).all()
        )

        return {
            "product_id": product_id,
            "total_pending": status_counts.get(ReviewQueueStatus.PENDING, 0),
            "total_in_review": status_counts.get(ReviewQueueStatus.IN_REVIEW, 0),
            "total_approved": status_counts.get(ReviewQueueStatus.APPROVED, 0),
            "total_rejected": status_counts.get(ReviewQueueStatus.REJECTED, 0),
            "by_type": {
                "ideas": type_counts.get(ReviewQueueType.IDEA, 0),
                "competitive_alerts": type_counts.get(ReviewQueueType.COMPETITIVE_ALERT, 0),
                "reports": type_counts.get(ReviewQueueType.REPORT, 0),
            },
            "by_priority": {
                "urgent": priority_counts.get(ReviewQueuePriority.URGENT, 0),
                "high": priority_counts.get(ReviewQueuePriority.HIGH, 0),
                "normal": priority_counts.get(ReviewQueuePriority.NORMAL, 0),
                "low": priority_counts.get(ReviewQueuePriority.LOW, 0),
            },
        }

    # =========================================================================
    # Queue Actions
    # =========================================================================

    def assign_item(
        self,
        queue_item_id: int,
        assigned_to_user_id: int
    ) -> PMReviewQueue:
        """
        Assign a queue item to a user for review.

        Args:
            queue_item_id: ID of the queue item
            assigned_to_user_id: ID of the user to assign to

        Returns:
            Updated queue item
        """
        item = self.db.query(PMReviewQueue).get(queue_item_id)
        if not item:
            raise ValueError(f"Queue item not found: {queue_item_id}")

        item.assigned_to_user_id = assigned_to_user_id
        item.status = ReviewQueueStatus.IN_REVIEW
        self.db.commit()
        self.db.refresh(item)

        return item

    def start_review(
        self,
        queue_item_id: int,
        reviewer_user_id: int
    ) -> PMReviewQueue:
        """
        Mark a queue item as in review and assign to the reviewer.

        Args:
            queue_item_id: ID of the queue item
            reviewer_user_id: ID of the user starting review

        Returns:
            Updated queue item
        """
        item = self.db.query(PMReviewQueue).get(queue_item_id)
        if not item:
            raise ValueError(f"Queue item not found: {queue_item_id}")

        item.status = ReviewQueueStatus.IN_REVIEW
        item.assigned_to_user_id = reviewer_user_id
        self.db.commit()
        self.db.refresh(item)

        return item

    def approve_item(
        self,
        queue_item_id: int,
        reviewer_user_id: int,
        notes: Optional[str] = None,
        publish_idea: bool = True
    ) -> PMReviewQueue:
        """
        Approve a queue item.

        For ideas: Updates the idea's triage_status and optionally publishes.
        For alerts: Marks as acknowledged/reviewed.

        Args:
            queue_item_id: ID of the queue item
            reviewer_user_id: ID of the reviewing user
            notes: Optional review notes
            publish_idea: For ideas, whether to publish for voting

        Returns:
            Updated queue item
        """
        item = self.db.query(PMReviewQueue).get(queue_item_id)
        if not item:
            raise ValueError(f"Queue item not found: {queue_item_id}")

        # Update queue item
        item.status = ReviewQueueStatus.APPROVED
        item.reviewed_by_user_id = reviewer_user_id
        item.reviewed_at = datetime.utcnow()
        item.review_notes = notes
        item.review_action = "approve"

        # Handle type-specific actions
        if item.queue_type == ReviewQueueType.IDEA:
            idea = self.db.query(Idea).get(item.item_id)
            if idea:
                idea.triage_status = TriageStatus.APPROVED
                idea.reviewed_by_user_id = reviewer_user_id
                idea.reviewed_at = datetime.utcnow()
                idea.review_notes = notes
                if publish_idea:
                    idea.published_for_voting = True

        self.db.commit()
        self.db.refresh(item)

        return item

    def reject_item(
        self,
        queue_item_id: int,
        reviewer_user_id: int,
        notes: Optional[str] = None,
        reason: Optional[str] = None
    ) -> PMReviewQueue:
        """
        Reject a queue item.

        For ideas: Updates the idea's triage_status to rejected.
        For alerts: Marks as dismissed.

        Args:
            queue_item_id: ID of the queue item
            reviewer_user_id: ID of the reviewing user
            notes: Optional review notes
            reason: Reason for rejection

        Returns:
            Updated queue item
        """
        item = self.db.query(PMReviewQueue).get(queue_item_id)
        if not item:
            raise ValueError(f"Queue item not found: {queue_item_id}")

        # Update queue item
        item.status = ReviewQueueStatus.REJECTED
        item.reviewed_by_user_id = reviewer_user_id
        item.reviewed_at = datetime.utcnow()
        item.review_notes = notes or reason
        item.review_action = "reject"

        # Handle type-specific actions
        if item.queue_type == ReviewQueueType.IDEA:
            idea = self.db.query(Idea).get(item.item_id)
            if idea:
                idea.triage_status = TriageStatus.REJECTED
                idea.reviewed_by_user_id = reviewer_user_id
                idea.reviewed_at = datetime.utcnow()
                idea.review_notes = notes or reason
                idea.published_for_voting = False

        elif item.queue_type == ReviewQueueType.COMPETITIVE_ALERT:
            # Just mark as dismissed
            item.status = ReviewQueueStatus.DISMISSED

        self.db.commit()
        self.db.refresh(item)

        return item

    def defer_item(
        self,
        queue_item_id: int,
        reviewer_user_id: int,
        defer_until: Optional[datetime] = None,
        notes: Optional[str] = None
    ) -> PMReviewQueue:
        """
        Defer a queue item for later review.

        Args:
            queue_item_id: ID of the queue item
            reviewer_user_id: ID of the reviewing user
            defer_until: Optional date to resurface the item
            notes: Optional review notes

        Returns:
            Updated queue item
        """
        item = self.db.query(PMReviewQueue).get(queue_item_id)
        if not item:
            raise ValueError(f"Queue item not found: {queue_item_id}")

        item.status = ReviewQueueStatus.DEFERRED
        item.reviewed_by_user_id = reviewer_user_id
        item.reviewed_at = datetime.utcnow()
        item.review_notes = notes
        item.review_action = "defer"
        if defer_until:
            item.due_by = defer_until

        self.db.commit()
        self.db.refresh(item)

        return item

    # =========================================================================
    # Monitoring Configuration
    # =========================================================================

    def get_monitoring_config(self, product_id: int) -> Optional[MonitoringConfig]:
        """Get monitoring configuration for a product."""
        return self.db.query(MonitoringConfig).filter(
            MonitoringConfig.product_id == product_id
        ).first()

    def create_or_update_monitoring_config(
        self,
        product_id: int,
        enabled: bool = False,
        frequency: str = "weekly",
        **settings
    ) -> MonitoringConfig:
        """
        Create or update monitoring configuration for a product.

        Args:
            product_id: Product ID
            enabled: Whether monitoring is enabled
            frequency: Monitoring frequency ("daily", "weekly", "biweekly", "monthly")
            **settings: Additional settings to update

        Returns:
            The monitoring configuration
        """
        config = self.get_monitoring_config(product_id)

        if not config:
            config = MonitoringConfig(
                product_id=product_id,
                monitoring_enabled=enabled,
                monitoring_frequency=frequency,
            )
            self.db.add(config)
        else:
            config.monitoring_enabled = enabled
            config.monitoring_frequency = frequency

        # Update any additional settings
        for key, value in settings.items():
            if hasattr(config, key):
                setattr(config, key, value)

        self.db.commit()
        self.db.refresh(config)

        return config

    def get_products_due_for_monitoring(self) -> List[MonitoringConfig]:
        """
        Get all products that are due for monitoring.

        Returns products where:
        - Monitoring is enabled
        - next_scheduled_at is null or in the past
        """
        now = datetime.utcnow()

        return self.db.query(MonitoringConfig).filter(
            MonitoringConfig.monitoring_enabled == True,
            or_(
                MonitoringConfig.next_scheduled_at.is_(None),
                MonitoringConfig.next_scheduled_at <= now
            )
        ).all()
