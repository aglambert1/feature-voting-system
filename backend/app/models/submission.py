"""
Submission model for database.

This tracks manual idea submissions with the original freeform text
and the AI-structured version.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class Submission(Base):
    """
    Submission model tracking manual idea submissions.

    Stores the original freeform text the user typed,
    the AI-structured version, and any user edits.
    """

    __tablename__ = "submissions"

    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign keys
    idea_id = Column(Integer, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False, unique=True)
    submitter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Original input
    original_freeform_text = Column(Text, nullable=False)

    # AI processing
    ai_structured_version = Column(JSON, nullable=True)  # {what, why, use_case} from AI
    user_edits = Column(JSON, nullable=True)  # Track what user changed from AI suggestions
    structuring_time_seconds = Column(Integer, nullable=True)  # How long AI took to structure

    # Timestamps
    submitted_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Metadata
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(Text, nullable=True)

    # Relationships
    idea = relationship("Idea", back_populates="submission")
    submitter = relationship("User", back_populates="submissions")

    def __repr__(self):
        return f"<Submission(id={self.id}, idea_id={self.idea_id}, submitter_id={self.submitter_id})>"
