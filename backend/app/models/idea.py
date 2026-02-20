"""
Idea model for database.

This defines the structure of the 'ideas' table in the database.
Ideas can come from multiple sources: manual submissions, competitor features,
CRM imports, support tickets, etc.

Phase 3 Enhancement: Unified idea model with consolidated status.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, Boolean, Float, JSON, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class SourceType(str, enum.Enum):
    """
    Source of the idea.

    - CUSTOMER_SUBMISSION: User submitted this idea manually
    - COMPETITOR_AUTOMATED: Extracted from competitor feature
    - CRM_IMPORT: Imported from CRM system (future)
    - SUPPORT_TICKET: Extracted from support ticket (future)
    - EXTERNAL_SUBMISSION: Synced from external idea system (Aha!, Jira, etc.)
    """
    CUSTOMER_SUBMISSION = "customer_submission"
    COMPETITOR_AUTOMATED = "competitor_automated"
    CRM_IMPORT = "crm_import"
    SUPPORT_TICKET = "support_ticket"
    EXTERNAL_SUBMISSION = "external_submission"

    # Legacy value mapping
    @classmethod
    def from_legacy(cls, value: str) -> "SourceType":
        """Convert legacy source type values."""
        legacy_map = {
            "manual_submission": cls.CUSTOMER_SUBMISSION,
            "manual": cls.CUSTOMER_SUBMISSION,
        }
        return legacy_map.get(value, cls(value))


class IdeaStatus(str, enum.Enum):
    """
    Unified idea status.

    Each status has a default is_active value (configurable per-product).
    Default visibility: only ACCEPTED is visible (is_active=True).

    - PENDING: Awaiting AI triage (is_active=False)
    - ACCEPTED: Approved for voting (is_active=True)
    - NEEDS_REVIEW: AI flagged, awaiting PO review (is_active=False)
    - DUPLICATE: Matches existing idea (is_active=False)
    - MERGED: Combined with another idea (is_active=False, future)
    - FEATURE_EXISTS: Already exists in product (is_active=False)
    - NOT_APPROPRIATE: Rejected/off-topic (is_active=False)
    """
    PENDING = "pending"
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"
    DUPLICATE = "duplicate"
    MERGED = "merged"
    FEATURE_EXISTS = "feature_exists"
    NOT_APPROPRIATE = "not_appropriate"


# Default visibility mapping for statuses
# Products can override this via status_visibility_config
DEFAULT_STATUS_VISIBILITY = {
    IdeaStatus.PENDING: False,
    IdeaStatus.ACCEPTED: True,
    IdeaStatus.NEEDS_REVIEW: False,
    IdeaStatus.DUPLICATE: False,
    IdeaStatus.MERGED: False,
    IdeaStatus.FEATURE_EXISTS: False,
    IdeaStatus.NOT_APPROPRIATE: False,
}


class Idea(Base):
    """
    Unified idea model for all sources.

    Each idea has structured content (what/why/use_case), tracks its source,
    and includes triage metadata for the review workflow.
    """

    __tablename__ = "ideas"

    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Structured content
    title = Column(String(255), nullable=False, index=True)
    what_description = Column(Text, nullable=False)  # What is the feature?
    why_description = Column(Text, nullable=False)    # Why is it valuable?
    use_case_description = Column(Text, nullable=False)  # How would it be used?

    # Source tracking
    source_type = Column(Enum(SourceType), nullable=False, default=SourceType.CUSTOMER_SUBMISSION)
    source_metadata = Column(JSON, nullable=True)  # Flexible metadata per source type
    # For competitor ideas: {"competitor_id": 123, "feature_id": 456, "competitor_name": "..."}
    # For CRM imports: {"crm_id": "...", "crm_type": "salesforce", "opportunity_id": "..."}
    # For support tickets: {"ticket_id": "...", "customer_email": "...", "ticket_subject": "..."}
    # For external submissions: {"external_url": "https://app.aha.io/ideas/...", "workflow_status": "..."}

    # External system tracking (for ideas synced from Aha!, Jira, etc.)
    external_id = Column(String(255), nullable=True, index=True)
    external_source = Column(String(100), nullable=True, index=True)  # e.g., "aha", "jira", "productboard"

    submitter_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Null for automated ideas
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="CASCADE"), nullable=False, index=True)

    # Categorization
    category = Column(String(100), nullable=True)
    auto_categorized = Column(Boolean, default=False, nullable=False)  # True if category was set by AI

    # Unified status (replaces old status + triage_status)
    status = Column(Enum(IdeaStatus), default=IdeaStatus.PENDING, nullable=False, index=True)

    # Visibility - derived from status but stored for efficient querying
    # Set based on product's status_visibility_config when status changes
    is_active = Column(Boolean, default=False, nullable=False)

    # Triage metadata (AI analysis results - still useful for display)
    triage_confidence = Column(Float, nullable=True)  # 0.0-1.0, AI confidence in recommendation
    triage_reasoning = Column(Text, nullable=True)  # AI explanation for recommendation
    triage_recommendation = Column(Text, nullable=True)  # Recommended action as string

    # Duplicate detection
    duplicate_of_idea_id = Column(Integer, ForeignKey("ideas.id"), nullable=True)
    similarity_score = Column(Float, nullable=True)  # 0.0-1.0, similarity to duplicate_of_idea

    # Competitive context (from triage)
    competitive_context = Column(JSON, nullable=True)
    # {"competitors_with_feature": ["Asana", "Monday"], "competitive_urgency": "high"}

    # Auto-response (generated for customer acknowledgment)
    auto_response_text = Column(Text, nullable=True)

    # PM review notes
    review_notes = Column(Text, nullable=True)  # PM notes on decision

    # Queue job reference (for tracking)
    triage_job_id = Column(Integer, ForeignKey("queue_jobs.id"), nullable=True)

    # Competitive source traceability
    source_feature_ids = Column(JSON, nullable=True)  # [feature_id, ...] for tracing back to source features

    # Lifecycle status (post-acceptance stages like "On Roadmap", "Delivered")
    lifecycle_status_id = Column(Integer, ForeignKey("idea_lifecycle_statuses.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    submitter = relationship("User", foreign_keys=[submitter_id], back_populates="ideas")
    votes = relationship("Vote", back_populates="idea", cascade="all, delete-orphan")
    submission = relationship("Submission", back_populates="idea", uselist=False, cascade="all, delete-orphan")
    product = relationship("CIProduct", backref="ideas")
    duplicate_of = relationship("Idea", remote_side=[id], foreign_keys=[duplicate_of_idea_id])
    triage_job = relationship("QueueJob", foreign_keys=[triage_job_id])
    comments = relationship("IdeaComment", back_populates="idea", cascade="all, delete-orphan", order_by="IdeaComment.created_at")
    status_history = relationship("IdeaStatusHistory", back_populates="idea", cascade="all, delete-orphan", order_by="IdeaStatusHistory.created_at")
    lifecycle_status = relationship("IdeaLifecycleStatus", foreign_keys=[lifecycle_status_id])

    __table_args__ = (
        UniqueConstraint('external_id', 'external_source', 'product_id', name='unique_external_idea'),
    )

    def __repr__(self):
        return f"<Idea(id={self.id}, title='{self.title}', source='{self.source_type}', status='{self.status}')>"

    @property
    def can_vote(self) -> bool:
        """Check if idea is open for voting."""
        return self.status == IdeaStatus.ACCEPTED

    @property
    def is_triaged(self) -> bool:
        """Check if idea has been triaged (not pending)."""
        return self.status != IdeaStatus.PENDING

    @property
    def needs_pm_review(self) -> bool:
        """Check if idea needs PM review."""
        return self.status == IdeaStatus.NEEDS_REVIEW

    @property
    def is_from_competitor(self) -> bool:
        """Check if idea originated from competitor intelligence."""
        return self.source_type == SourceType.COMPETITOR_AUTOMATED

    @staticmethod
    def get_default_is_active_for_status(status: IdeaStatus) -> bool:
        """Return default is_active value for a given status."""
        return DEFAULT_STATUS_VISIBILITY.get(status, False)

    def to_dict(self) -> dict:
        """Return idea fields as dictionary for API responses."""
        return {
            "id": self.id,
            "title": self.title,
            "source_type": self.source_type.value,
            "category": self.category,
            "status": self.status.value,
            "is_active": self.is_active,
            "triage_confidence": self.triage_confidence,
            "triage_reasoning": self.triage_reasoning,
            "triage_recommendation": self.triage_recommendation,
            "duplicate_of_idea_id": self.duplicate_of_idea_id,
            "similarity_score": self.similarity_score,
            "competitive_context": self.competitive_context,
            "auto_response_text": self.auto_response_text,
            "review_notes": self.review_notes,
            "source_feature_ids": self.source_feature_ids,
            "external_id": self.external_id,
            "external_source": self.external_source,
            "lifecycle_status_id": self.lifecycle_status_id,
            "lifecycle_status_name": self.lifecycle_status.name if self.lifecycle_status else None,
            "lifecycle_status_color": self.lifecycle_status.color if self.lifecycle_status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
