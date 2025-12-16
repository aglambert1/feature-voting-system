"""
Idea model for database.

This defines the structure of the 'ideas' table in the database.
Ideas can come from manual submissions or competitor features (future).
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class SourceType(str, enum.Enum):
    """
    Source of the idea.

    - MANUAL: User submitted this idea manually
    - COMPETITOR: Extracted from competitor (future feature)
    """
    MANUAL = "manual_submission"
    COMPETITOR = "competitor_automated"


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


class Idea(Base):
    """
    Idea model representing a feature idea.

    Each idea has structured content (what/why/use_case) and tracks its source.
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
    source_type = Column(Enum(SourceType), nullable=False, default=SourceType.MANUAL)
    submitter_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Null for competitor ideas
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="CASCADE"), nullable=False, index=True)

    # Categorization
    category = Column(String(100), nullable=True)

    # Status
    status = Column(Enum(IdeaStatus), default=IdeaStatus.ACTIVE, nullable=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    submitter = relationship("User", back_populates="ideas")
    votes = relationship("Vote", back_populates="idea", cascade="all, delete-orphan")
    submission = relationship("Submission", back_populates="idea", uselist=False, cascade="all, delete-orphan")
    product = relationship("CIProduct", backref="ideas")

    def __repr__(self):
        return f"<Idea(id={self.id}, title='{self.title}', source='{self.source_type}')>"
