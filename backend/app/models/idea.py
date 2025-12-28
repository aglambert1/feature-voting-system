"""
Idea model for database.

This defines the structure of the 'ideas' table in the database.
Ideas can come from multiple sources: manual submissions, competitor features,
CRM imports, support tickets, etc.

Phase 3 Enhancement: Unified idea model with triage support.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, Boolean, Float, JSON
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
    """
    CUSTOMER_SUBMISSION = "customer_submission"
    COMPETITOR_AUTOMATED = "competitor_automated"
    CRM_IMPORT = "crm_import"
    SUPPORT_TICKET = "support_ticket"

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
    Status of an idea.

    - ACTIVE: Currently active and votable
    - ARCHIVED: Hidden from main view
    - MERGED: Merged with another idea
    - IMPLEMENTED: Feature has been implemented
    """
    ACTIVE = "active"
    ARCHIVED = "archived"
    MERGED = "merged"
    IMPLEMENTED = "implemented"


class TriageStatus(str, enum.Enum):
    """
    Triage status for idea review workflow.

    - PENDING: Awaiting triage processing
    - AUTO_APPROVED: Automatically approved (high confidence)
    - NEEDS_REVIEW: Requires PM review
    - APPROVED: PM approved for voting
    - REJECTED: PM rejected
    - DUPLICATE: Marked as duplicate of another idea
    """
    PENDING = "pending"
    AUTO_APPROVED = "auto_approved"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class TriageAction(str, enum.Enum):
    """
    Recommended triage actions from IdeaTriageAgent.
    """
    APPROVE = "approve"
    MERGE = "merge"
    REVIEW = "review"
    REJECT = "reject"


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

    submitter_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Null for automated ideas
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="CASCADE"), nullable=False, index=True)

    # Categorization
    category = Column(String(100), nullable=True)
    auto_categorized = Column(Boolean, default=False, nullable=False)  # True if category was set by AI

    # Status
    status = Column(Enum(IdeaStatus), default=IdeaStatus.ACTIVE, nullable=False)

    # Triage workflow (Phase 3)
    triage_status = Column(Enum(TriageStatus), default=TriageStatus.PENDING, nullable=False, index=True)
    triage_confidence = Column(Float, nullable=True)  # 0.0-1.0, AI confidence in recommendation
    triage_reasoning = Column(Text, nullable=True)  # AI explanation for recommendation
    triage_recommendation = Column(Enum(TriageAction), nullable=True)  # Recommended action

    # Duplicate detection
    duplicate_of_idea_id = Column(Integer, ForeignKey("ideas.id"), nullable=True)
    similarity_score = Column(Float, nullable=True)  # 0.0-1.0, similarity to duplicate_of_idea

    # Competitive context (from triage)
    competitive_context = Column(JSON, nullable=True)
    # {"competitors_with_feature": ["Asana", "Monday"], "competitive_urgency": "high"}

    # Auto-response (generated for customer acknowledgment)
    auto_response_text = Column(Text, nullable=True)

    # PM review
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)  # PM notes on decision
    published_for_voting = Column(Boolean, default=False, nullable=False)

    # Queue job reference (for tracking)
    triage_job_id = Column(Integer, ForeignKey("queue_jobs.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    submitter = relationship("User", foreign_keys=[submitter_id], back_populates="ideas")
    reviewer = relationship("User", foreign_keys=[reviewed_by_user_id], overlaps="reviewed_ideas")
    votes = relationship("Vote", back_populates="idea", cascade="all, delete-orphan")
    submission = relationship("Submission", back_populates="idea", uselist=False, cascade="all, delete-orphan")
    product = relationship("CIProduct", backref="ideas")
    duplicate_of = relationship("Idea", remote_side=[id], foreign_keys=[duplicate_of_idea_id])
    triage_job = relationship("QueueJob", foreign_keys=[triage_job_id])

    def __repr__(self):
        return f"<Idea(id={self.id}, title='{self.title}', source='{self.source_type}', triage='{self.triage_status}')>"

    @property
    def is_triaged(self) -> bool:
        """Check if idea has been triaged."""
        return self.triage_status not in (TriageStatus.PENDING,)

    @property
    def needs_pm_review(self) -> bool:
        """Check if idea needs PM review."""
        return self.triage_status == TriageStatus.NEEDS_REVIEW

    @property
    def is_from_competitor(self) -> bool:
        """Check if idea originated from competitor intelligence."""
        return self.source_type == SourceType.COMPETITOR_AUTOMATED

    def to_triage_dict(self) -> dict:
        """Return triage-relevant fields as dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "source_type": self.source_type.value,
            "category": self.category,
            "triage_status": self.triage_status.value,
            "triage_confidence": self.triage_confidence,
            "triage_reasoning": self.triage_reasoning,
            "triage_recommendation": self.triage_recommendation.value if self.triage_recommendation else None,
            "duplicate_of_idea_id": self.duplicate_of_idea_id,
            "similarity_score": self.similarity_score,
            "competitive_context": self.competitive_context,
            "auto_response_text": self.auto_response_text,
            "reviewed_by_user_id": self.reviewed_by_user_id,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "published_for_voting": self.published_for_voting,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
