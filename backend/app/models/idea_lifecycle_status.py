"""
IdeaLifecycleStatus model for tracking post-acceptance idea stages.

Represents lifecycle stages beyond the triage workflow (e.g., "On Roadmap", "Delivered").
These are system-wide, admin-configurable statuses with a max of 3.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func

from app.database import Base


class IdeaLifecycleStatus(Base):
    """
    A lifecycle status that ideas can progress through after acceptance.

    Separate from the triage IdeaStatus enum — these represent what happens
    after an idea is accepted (e.g., planned, in development, delivered).
    """
    __tablename__ = "idea_lifecycle_statuses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)       # "On Roadmap"
    slug = Column(String(100), nullable=False, unique=True)       # "on_roadmap"
    color = Column(String(7), nullable=False, default="#3B82F6")  # hex color
    position = Column(Integer, nullable=False, default=0)         # display ordering
    is_default = Column(Boolean, nullable=False, default=False)   # shipped with system
    is_active = Column(Boolean, nullable=False, default=True)     # can be disabled
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<IdeaLifecycleStatus(id={self.id}, name='{self.name}', slug='{self.slug}')>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "color": self.color,
            "position": self.position,
            "is_default": self.is_default,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
