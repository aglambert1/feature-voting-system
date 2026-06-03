"""
Vote model for database.

This defines the structure of the 'votes' table in the database.
Users can upvote (+1) ideas or remove their vote.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class Vote(Base):
    """
    Vote model representing a user's vote on an idea.

    Each user can only vote once per idea (upvote). Voting again removes the vote.
    """

    __tablename__ = "votes"

    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Foreign keys
    idea_id = Column(Integer, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Vote value: 1 for upvote (only valid value)
    vote_value = Column(Integer, nullable=False)

    # Timestamps
    voted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    idea = relationship("Idea", back_populates="votes")
    user = relationship("User", back_populates="votes")

    # Constraints
    __table_args__ = (
        UniqueConstraint('idea_id', 'user_id', name='unique_user_idea_vote'),
        CheckConstraint('vote_value = 1', name='check_vote_value'),
    )

    def __repr__(self):
        return f"<Vote(id={self.id}, user_id={self.user_id}, idea_id={self.idea_id}, value={self.vote_value})>"
