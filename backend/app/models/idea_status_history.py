"""
IdeaStatusHistory model for tracking status changes on ideas.

This provides an audit trail of all status changes, recording:
- Who changed the status
- What the status changed from/to
- When the change occurred
- Whether it was a manual or automated change
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum as SQLAlchemyEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.idea import IdeaStatus


class IdeaStatusHistory(Base):
    """
    History record for an idea status change.

    Tracks all status transitions including:
    - Initial submission (pending)
    - Agent recommendations
    - PO decisions
    - Any subsequent edits
    """
    __tablename__ = "idea_status_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    idea_id = Column(Integer, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False, index=True)

    # Status change details
    previous_status = Column(SQLAlchemyEnum(IdeaStatus), nullable=True)  # null for initial creation
    new_status = Column(SQLAlchemyEnum(IdeaStatus), nullable=False)

    # Who made the change
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Change type
    is_automated = Column(Boolean, default=False, nullable=False)  # True if changed by agent
    change_source = Column(String(50), nullable=False)  # 'submission', 'agent_triage', 'po_response', 'po_edit'

    # Additional context
    comment = Column(Text, nullable=True)  # Optional explanation
    confidence = Column(Integer, nullable=True)  # Agent confidence (0-100) if automated

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    idea = relationship("Idea", back_populates="status_history")
    changed_by = relationship("User")

    def __repr__(self):
        return f"<IdeaStatusHistory(id={self.id}, idea_id={self.idea_id}, {self.previous_status} -> {self.new_status})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "idea_id": self.idea_id,
            "previous_status": self.previous_status.value if self.previous_status else None,
            "new_status": self.new_status.value,
            "changed_by_user_id": self.changed_by_user_id,
            "is_automated": self.is_automated,
            "change_source": self.change_source,
            "comment": self.comment,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
