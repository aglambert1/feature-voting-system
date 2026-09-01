"""
Cost tracking models for LLM usage monitoring.

This module defines the database models for tracking LLM API usage,
token counts, and estimated costs per user and operation type.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class OperationType(str, enum.Enum):
    """
    Types of LLM operations for cost categorization.

    Each operation type corresponds to a distinct use case in the system.
    """
    IDEA_TRIAGE = "idea_triage"
    IDEA_STRUCTURING = "idea_structuring"
    PRODUCT_ANALYSIS = "product_analysis"
    COMPETITOR_DISCOVERY = "competitor_discovery"
    COMPETITOR_FEATURE_EXTRACTION = "competitor_feature_extraction"
    GAP_ANALYSIS = "gap_analysis"
    OPPORTUNITY_SYNTHESIS = "opportunity_synthesis"
    FUNCTIONAL_AUDIT = "functional_audit"
    LANDSCAPE_SYNTHESIS = "landscape_synthesis"
    ACTIVITY_INSIGHT = "activity_insight"
    INTERNAL_DISCOVERY = "internal_discovery"
    SELF_ASSESSMENT = "self_assessment"
    OTHER = "other"


class LLMUsageLog(Base):
    """
    Log of LLM API usage for cost tracking.

    Records every LLM call with token counts, estimated cost,
    and context about who made the call and for what purpose.
    """
    __tablename__ = "llm_usage_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # User context
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Operation context
    operation_type = Column(Enum(OperationType), nullable=False, index=True)

    # Token counts
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)

    # Cost calculation
    model = Column(String(100), nullable=False)
    estimated_cost_usd = Column(Float, nullable=False)

    # Additional context
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="SET NULL"), nullable=True, index=True)
    job_id = Column(String(36), nullable=True, index=True)  # Link to QueueJob.job_uuid if applicable

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Relationships
    user = relationship("User", backref="llm_usage_logs")
    product = relationship("CIProduct", backref="llm_usage_logs")

    def __repr__(self):
        return f"<LLMUsageLog(id={self.id}, op={self.operation_type}, cost=${self.estimated_cost_usd:.4f})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "operation_type": self.operation_type.value if self.operation_type else None,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "model": self.model,
            "estimated_cost_usd": self.estimated_cost_usd,
            "product_id": self.product_id,
            "job_id": self.job_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
