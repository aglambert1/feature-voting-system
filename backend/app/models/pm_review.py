"""
PM Review Queue models for Phase 4.

This module defines database models for:
1. PMReviewQueue - Unified queue for all items needing PM review
2. CompetitorSnapshot - Historical snapshots for change detection
3. Alert types and configurations

The PM Review Queue consolidates:
- Ideas needing review
- Competitive alerts (feature changes)
- Generated reports
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    JSON, Enum, Boolean, Float
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class ReviewQueueType(str, enum.Enum):
    """
    Types of items in the PM review queue.
    """
    IDEA = "idea"                      # New idea needing review
    COMPETITIVE_ALERT = "competitive_alert"  # Competitive change alert
    REPORT = "report"                  # Generated report for review


class ReviewQueuePriority(str, enum.Enum):
    """
    Priority levels for review queue items.
    """
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ReviewQueueStatus(str, enum.Enum):
    """
    Status of a review queue item.
    """
    PENDING = "pending"        # Awaiting review
    IN_REVIEW = "in_review"    # Currently being reviewed
    APPROVED = "approved"      # Approved by PM
    REJECTED = "rejected"      # Rejected by PM
    DEFERRED = "deferred"      # Deferred for later
    DISMISSED = "dismissed"    # Dismissed (for alerts)


class AlertType(str, enum.Enum):
    """
    Types of competitive alerts.

    From agent_competitive_monitor.md spec.
    """
    NEW_COMPETITOR = "new_competitor"         # New competitor entered market
    COMPETITOR_REMOVED = "competitor_removed" # Competitor no longer active
    MAJOR_FEATURE_LAUNCH = "major_feature_launch"  # Significant new feature
    FEATURE_REMOVED = "feature_removed"       # Feature was removed
    PRICING_CHANGE = "pricing_change"         # Pricing model changed
    TREND_DETECTED = "trend_detected"         # Market trend identified


class PMReviewQueue(Base):
    """
    Unified PM review queue for all item types.

    Provides a single interface for PMs to review:
    - Ideas that need manual approval
    - Competitive alerts from monitoring
    - Generated reports

    Polymorphic reference pattern: item_type + item_id can reference
    different tables (ideas, competitor_snapshots, reports).
    """
    __tablename__ = "pm_review_queue"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Queue type and status
    queue_type = Column(Enum(ReviewQueueType), nullable=False, index=True)
    status = Column(Enum(ReviewQueueStatus), nullable=False, default=ReviewQueueStatus.PENDING, index=True)
    priority = Column(Enum(ReviewQueuePriority), nullable=False, default=ReviewQueuePriority.NORMAL)

    # Polymorphic reference to the item being reviewed
    item_type = Column(String(50), nullable=False, index=True)  # "idea", "competitor_snapshot", "report"
    item_id = Column(Integer, nullable=False, index=True)

    # Title/summary for quick scanning
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=True)

    # For competitive alerts
    alert_type = Column(Enum(AlertType), nullable=True)
    alert_severity = Column(String(50), nullable=True)  # "info", "warning", "critical"

    # Additional item metadata (note: 'metadata' is reserved in SQLAlchemy)
    item_metadata = Column(JSON, nullable=True)
    # Examples:
    # For ideas: {"source_type": "customer_submission", "confidence": 0.85}
    # For alerts: {"competitor_name": "Asana", "feature_count": 3}
    # For reports: {"report_type": "competitive_landscape", "period": "weekly"}

    # Relationships
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    queue_job_id = Column(Integer, ForeignKey("queue_jobs.id"), nullable=True)

    # Review tracking
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    review_action = Column(String(50), nullable=True)  # Action taken: "approve", "reject", etc.

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    due_by = Column(DateTime, nullable=True)  # Optional due date for prioritization

    def __repr__(self):
        return f"<PMReviewQueue(id={self.id}, type={self.queue_type}, status={self.status})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "queue_type": self.queue_type.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "item_type": self.item_type,
            "item_id": self.item_id,
            "title": self.title,
            "summary": self.summary,
            "alert_type": self.alert_type.value if self.alert_type else None,
            "alert_severity": self.alert_severity,
            "metadata": self.item_metadata,
            "product_id": self.product_id,
            "assigned_to_user_id": self.assigned_to_user_id,
            "reviewed_by_user_id": self.reviewed_by_user_id,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_notes": self.review_notes,
            "review_action": self.review_action,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "due_by": self.due_by.isoformat() if self.due_by else None,
        }


class CompetitorSnapshot(Base):
    """
    Historical snapshots of competitor features for change detection.

    Each monitoring run creates a snapshot of the current competitor state.
    Snapshots are compared to detect:
    - New features added
    - Features removed
    - Features modified
    - New competitors discovered

    This enables the "what changed" differential view for PMs.
    """
    __tablename__ = "competitor_snapshots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Reference to the competitor being monitored
    product_competitor_id = Column(
        Integer,
        ForeignKey("product_competitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Snapshot timing
    snapshot_date = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    # Snapshot data
    features_json = Column(JSON, nullable=False)
    # Structure: [{"id": 1, "name": "...", "description": "...", "category": "..."}]

    features_hash = Column(String(64), nullable=False)  # SHA-256 for quick comparison
    feature_count = Column(Integer, nullable=False, default=0)

    # Change detection results (compared to previous snapshot)
    changes_detected = Column(JSON, nullable=True)
    # Structure: {
    #   "new_features": [{"name": "...", "description": "..."}],
    #   "removed_features": [{"id": 1, "name": "..."}],
    #   "modified_features": [{"id": 1, "name": "...", "changes": {...}}],
    #   "is_new_competitor": false
    # }

    has_changes = Column(Boolean, nullable=False, default=False, index=True)
    change_summary = Column(Text, nullable=True)  # Human-readable summary

    # Alert generation
    alert_generated = Column(Boolean, nullable=False, default=False)
    alert_type = Column(Enum(AlertType), nullable=True)
    review_queue_id = Column(Integer, ForeignKey("pm_review_queue.id"), nullable=True)

    # Queue job that created this snapshot
    queue_job_id = Column(Integer, ForeignKey("queue_jobs.id"), nullable=True)

    # Reference to previous snapshot for chaining
    previous_snapshot_id = Column(Integer, ForeignKey("competitor_snapshots.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    product_competitor = relationship("ProductCompetitor", backref="snapshots")
    previous_snapshot = relationship("CompetitorSnapshot", remote_side=[id], foreign_keys=[previous_snapshot_id])

    def __repr__(self):
        return f"<CompetitorSnapshot(id={self.id}, competitor_id={self.product_competitor_id}, has_changes={self.has_changes})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "product_competitor_id": self.product_competitor_id,
            "snapshot_date": self.snapshot_date.isoformat() if self.snapshot_date else None,
            "feature_count": self.feature_count,
            "features_hash": self.features_hash,
            "has_changes": self.has_changes,
            "change_summary": self.change_summary,
            "changes_detected": self.changes_detected,
            "alert_generated": self.alert_generated,
            "alert_type": self.alert_type.value if self.alert_type else None,
            "previous_snapshot_id": self.previous_snapshot_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MonitoringConfig(Base):
    """
    Per-product monitoring configuration.

    DEPRECATED: This model is replaced by CompetitiveAgentConfig in
    app/models/competitive_agent.py. Use the new model for all new features.

    Stores settings for automated competitive monitoring:
    - Enabled/disabled status
    - Monitoring frequency
    - Alert thresholds
    - Notification preferences
    """
    __tablename__ = "monitoring_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    product_id = Column(
        Integer,
        ForeignKey("ci_products.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    # Monitoring settings
    monitoring_enabled = Column(Boolean, nullable=False, default=False)
    monitoring_frequency = Column(String(50), nullable=False, default="weekly")
    # Options: "daily", "weekly", "biweekly", "monthly"

    # Last monitoring run
    last_monitored_at = Column(DateTime, nullable=True)
    next_scheduled_at = Column(DateTime, nullable=True)

    # Alert configuration
    alert_on_new_features = Column(Boolean, nullable=False, default=True)
    alert_on_removed_features = Column(Boolean, nullable=False, default=True)
    alert_on_new_competitors = Column(Boolean, nullable=False, default=True)
    min_feature_change_threshold = Column(Integer, nullable=False, default=1)
    # Minimum number of feature changes to trigger an alert

    # Auto-generate ideas from competitor features
    auto_generate_ideas = Column(Boolean, nullable=False, default=False)
    auto_idea_confidence_threshold = Column(Float, nullable=False, default=0.8)

    # Notification settings
    notify_product_owners = Column(Boolean, nullable=False, default=True)
    notification_settings = Column(JSON, nullable=True)
    # Structure: {"email": true, "slack": false, "webhook_url": null}

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    product = relationship("CIProduct", backref="monitoring_config", uselist=False)

    def __repr__(self):
        return f"<MonitoringConfig(product_id={self.product_id}, enabled={self.monitoring_enabled}, frequency={self.monitoring_frequency})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "monitoring_enabled": self.monitoring_enabled,
            "monitoring_frequency": self.monitoring_frequency,
            "last_monitored_at": self.last_monitored_at.isoformat() if self.last_monitored_at else None,
            "next_scheduled_at": self.next_scheduled_at.isoformat() if self.next_scheduled_at else None,
            "alert_on_new_features": self.alert_on_new_features,
            "alert_on_removed_features": self.alert_on_removed_features,
            "alert_on_new_competitors": self.alert_on_new_competitors,
            "min_feature_change_threshold": self.min_feature_change_threshold,
            "auto_generate_ideas": self.auto_generate_ideas,
            "auto_idea_confidence_threshold": self.auto_idea_confidence_threshold,
            "notify_product_owners": self.notify_product_owners,
            "notification_settings": self.notification_settings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
