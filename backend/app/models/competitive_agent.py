"""
Competitive Agent models for the restructured competitive intelligence system.

This module defines database models for:
1. CompetitiveAgentConfig - Unified configuration for competitive analysis agent

The Competitive Analysis Agent uses these models to store configuration.
Analysis results are stored in CompetitorFunctionalReport
(see competitive_reports.py) and the unified SynthesisReport
(see synthesis.py).
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey,
    Enum, Boolean
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class AgentMode(str, enum.Enum):
    """
    Agent execution modes.

    - MANUAL: Only runs when PO explicitly triggers
    - SCHEDULED: Periodic execution (daily/weekly/monthly)
    """
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class CompetitiveAgentConfig(Base):
    """
    Configuration for the Competitive Analysis Agent.

    One config per product. Controls discovery, deep analysis, and intensity settings.
    Does NOT duplicate Idea Triage settings - uses existing CIProduct.idea_triage_* fields.
    """
    __tablename__ = "competitive_agent_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(
        Integer,
        ForeignKey("ci_products.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    # === Product Analysis Settings ===
    product_analysis_mode = Column(Enum(AgentMode), nullable=False, default=AgentMode.MANUAL)
    product_analysis_schedule = Column(String(50), nullable=True)  # "daily", "weekly", "monthly"
    product_analysis_next_run = Column(DateTime(timezone=True), nullable=True)
    product_analysis_last_run = Column(DateTime(timezone=True), nullable=True)

    # === Competitor Discovery Settings ===
    competitor_discovery_mode = Column(Enum(AgentMode), nullable=False, default=AgentMode.MANUAL)
    competitor_discovery_schedule = Column(String(50), nullable=True)
    competitor_discovery_next_run = Column(DateTime(timezone=True), nullable=True)
    competitor_discovery_last_run = Column(DateTime(timezone=True), nullable=True)
    alert_on_new_competitors = Column(Boolean, nullable=False, default=True)
    alert_on_disappeared_competitors = Column(Boolean, nullable=False, default=True)

    # === Deep Analysis Settings (Feature Extraction + Strategic Analysis) ===
    # Deep analysis runs for all competitors marked with tracked=True
    deep_analysis_mode = Column(Enum(AgentMode), nullable=False, default=AgentMode.MANUAL)
    deep_analysis_schedule = Column(String(50), nullable=True)
    deep_analysis_next_run = Column(DateTime(timezone=True), nullable=True)
    deep_analysis_last_run = Column(DateTime(timezone=True), nullable=True)

    # === General ===
    # Auto-idea-generation settings used to live here as `intensity_*` columns.
    # The JTBD redesign (PR #33) moved them onto SynthesisConfig
    # (auto_generate_ideas + idea_priority_threshold), and those columns were
    # dropped in n4o5p6q7r8s9.
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship
    product = relationship("CIProduct", back_populates="competitive_agent_config")

    def __repr__(self):
        return f"<CompetitiveAgentConfig(product_id={self.product_id}, enabled={self.enabled})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_analysis_mode": self.product_analysis_mode.value if self.product_analysis_mode else None,
            "product_analysis_schedule": self.product_analysis_schedule,
            "product_analysis_next_run": self.product_analysis_next_run.isoformat() if self.product_analysis_next_run else None,
            "product_analysis_last_run": self.product_analysis_last_run.isoformat() if self.product_analysis_last_run else None,
            "competitor_discovery_mode": self.competitor_discovery_mode.value if self.competitor_discovery_mode else None,
            "competitor_discovery_schedule": self.competitor_discovery_schedule,
            "competitor_discovery_next_run": self.competitor_discovery_next_run.isoformat() if self.competitor_discovery_next_run else None,
            "competitor_discovery_last_run": self.competitor_discovery_last_run.isoformat() if self.competitor_discovery_last_run else None,
            "alert_on_new_competitors": self.alert_on_new_competitors,
            "alert_on_disappeared_competitors": self.alert_on_disappeared_competitors,
            "deep_analysis_mode": self.deep_analysis_mode.value if self.deep_analysis_mode else None,
            "deep_analysis_schedule": self.deep_analysis_schedule,
            "deep_analysis_next_run": self.deep_analysis_next_run.isoformat() if self.deep_analysis_next_run else None,
            "deep_analysis_last_run": self.deep_analysis_last_run.isoformat() if self.deep_analysis_last_run else None,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


