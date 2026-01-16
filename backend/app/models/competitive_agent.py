"""
Competitive Agent models for the restructured competitive intelligence system.

This module defines database models for:
1. CompetitiveAgentConfig - Unified configuration for competitive analysis agent
2. FeatureCluster - Groups similar features across competitors
3. FeatureClusterMember - Links features to clusters
4. CompetitorPricingAnalysis - Pricing analysis results
5. CompetitorPositioningAnalysis - Positioning/messaging analysis results
6. CompetitorChangeEvent - Tracked competitor changes
7. CompetitorMomentumAnalysis - Growth and momentum signals
8. CompetitorFinancialsAnalysis - Financial data analysis

The Competitive Analysis Agent uses these models to store analysis results
and configuration. Feature clusters drive competitive intensity calculations
and auto-idea generation.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    JSON, Enum, Boolean, Float
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
    product_analysis_next_run = Column(DateTime, nullable=True)
    product_analysis_last_run = Column(DateTime, nullable=True)

    # === Competitor Discovery Settings ===
    competitor_discovery_mode = Column(Enum(AgentMode), nullable=False, default=AgentMode.MANUAL)
    competitor_discovery_schedule = Column(String(50), nullable=True)
    competitor_discovery_next_run = Column(DateTime, nullable=True)
    competitor_discovery_last_run = Column(DateTime, nullable=True)
    alert_on_new_competitors = Column(Boolean, nullable=False, default=True)
    alert_on_disappeared_competitors = Column(Boolean, nullable=False, default=True)

    # === Deep Analysis Settings (Feature Extraction + Strategic Analysis) ===
    # Deep analysis runs for all competitors marked with deep_analysis_enabled=True
    deep_analysis_mode = Column(Enum(AgentMode), nullable=False, default=AgentMode.MANUAL)
    deep_analysis_schedule = Column(String(50), nullable=True)
    deep_analysis_next_run = Column(DateTime, nullable=True)
    deep_analysis_last_run = Column(DateTime, nullable=True)

    # === Competitive Intensity Settings ===
    # Controls how features are clustered and when ideas are generated
    intensity_similarity_threshold = Column(Float, nullable=False, default=0.75)  # For clustering features
    intensity_idea_threshold = Column(Integer, nullable=False, default=3)  # Min competitors to auto-generate idea
    # Note: Once idea is generated, Idea Triage Agent handles dedup, auto-accept, etc.

    # === General ===
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

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
            "intensity_similarity_threshold": self.intensity_similarity_threshold,
            "intensity_idea_threshold": self.intensity_idea_threshold,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class FeatureCluster(Base):
    """
    Groups semantically similar features across competitors.

    Used for competitive intensity calculation and auto-idea generation.
    When multiple competitors have similar features, we cluster them and
    calculate competitive intensity (unique competitor count per cluster).
    """
    __tablename__ = "feature_clusters"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(
        Integer,
        ForeignKey("ci_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    cluster_name = Column(String(255), nullable=False)  # AI-generated representative name
    cluster_description = Column(Text, nullable=True)  # AI-generated summary of what this cluster represents
    centroid_embedding = Column(JSON, nullable=True)   # Average embedding for similarity matching

    # Intensity metrics
    competitor_count = Column(Integer, nullable=False, default=0)  # Number of unique competitors with this feature
    feature_count = Column(Integer, nullable=False, default=0)     # Total features in cluster

    # Idea generation tracking
    idea_generated = Column(Boolean, nullable=False, default=False)
    generated_idea_id = Column(Integer, ForeignKey("ideas.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    members = relationship("FeatureClusterMember", back_populates="cluster", cascade="all, delete-orphan")
    generated_idea = relationship("Idea", foreign_keys=[generated_idea_id])
    product = relationship("CIProduct", backref="feature_clusters")

    def __repr__(self):
        return f"<FeatureCluster(id={self.id}, name='{self.cluster_name}', intensity={self.competitor_count})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "cluster_name": self.cluster_name,
            "cluster_description": self.cluster_description,
            "competitor_count": self.competitor_count,
            "feature_count": self.feature_count,
            "idea_generated": self.idea_generated,
            "generated_idea_id": self.generated_idea_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class FeatureClusterMember(Base):
    """
    Links a competitor feature to a cluster.

    Tracks similarity score for each feature's membership in the cluster.
    """
    __tablename__ = "feature_cluster_members"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cluster_id = Column(
        Integer,
        ForeignKey("feature_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    feature_id = Column(
        Integer,
        ForeignKey("product_competitor_features.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    similarity_score = Column(Float, nullable=True)  # Similarity to cluster centroid
    added_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    cluster = relationship("FeatureCluster", back_populates="members")
    feature = relationship("ProductCompetitorFeature", backref="cluster_memberships")

    def __repr__(self):
        return f"<FeatureClusterMember(cluster_id={self.cluster_id}, feature_id={self.feature_id})>"


# NOTE: The following models have been deprecated and removed:
# - CompetitorPricingAnalysis
# - CompetitorPositioningAnalysis
# - CompetitorChangeEvent
# - CompetitorMomentumAnalysis
# - CompetitorFinancialsAnalysis
#
# They have been replaced by the new two-step analysis system:
# - CompetitorFunctionalReport (in competitive_reports.py)
# - LandscapeOpportunityReport (in competitive_reports.py)
