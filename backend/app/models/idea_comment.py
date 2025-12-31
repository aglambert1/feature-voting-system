"""
IdeaComment model for tracking comments on ideas.

This allows POs to leave comments explaining their response decisions,
and enables a history of discussions around an idea.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class IdeaComment(Base):
    """
    Comment on an idea.

    Used for:
    - PO response explanations
    - System-generated messages (e.g., from triage agent)
    - Discussion history
    """
    __tablename__ = "idea_comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    idea_id = Column(Integer, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Comment content
    comment_text = Column(Text, nullable=False)

    # System vs user comment
    is_system_generated = Column(Boolean, default=False, nullable=False)  # True if from agent

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    idea = relationship("Idea", back_populates="comments")
    user = relationship("User")

    def __repr__(self):
        return f"<IdeaComment(id={self.id}, idea_id={self.idea_id}, user_id={self.user_id})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "idea_id": self.idea_id,
            "user_id": self.user_id,
            "comment_text": self.comment_text,
            "is_system_generated": self.is_system_generated,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
