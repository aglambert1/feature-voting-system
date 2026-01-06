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

    # Strategic Analysis Toggles (which analyses to include in deep analysis)
    enable_pricing_analysis = Column(Boolean, nullable=False, default=True)
    enable_positioning_analysis = Column(Boolean, nullable=False, default=True)
    enable_changes_tracking = Column(Boolean, nullable=False, default=True)
    enable_momentum_analysis = Column(Boolean, nullable=False, default=True)
    enable_financials_analysis = Column(Boolean, nullable=False, default=False)  # Only if public/available

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
            "enable_pricing_analysis": self.enable_pricing_analysis,
            "enable_positioning_analysis": self.enable_positioning_analysis,
            "enable_changes_tracking": self.enable_changes_tracking,
            "enable_momentum_analysis": self.enable_momentum_analysis,
            "enable_financials_analysis": self.enable_financials_analysis,
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


class CompetitorPricingAnalysis(Base):
    """
    Pricing analysis results for a competitor.

    Stores extracted pricing model, tiers, and trial information.
    """
    __tablename__ = "competitor_pricing_analysis"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_competitor_id = Column(
        Integer,
        ForeignKey("product_competitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Pricing model
    pricing_model = Column(String(100), nullable=True)  # "freemium", "tiered", "usage_based", "flat_rate"
    has_free_tier = Column(Boolean, nullable=False, default=False)
    has_trial = Column(Boolean, nullable=False, default=False)
    trial_days = Column(Integer, nullable=True)

    # Pricing tiers structure
    # [{name: "Basic", price: 10, billing: "monthly", features: [...], limits: {...}}]
    pricing_tiers = Column(JSON, nullable=True)

    has_enterprise = Column(Boolean, nullable=False, default=False)
    enterprise_contact_required = Column(Boolean, nullable=False, default=False)

    # Source tracking
    source_url = Column(String(500), nullable=True)
    confidence = Column(Float, nullable=True)  # 0.0-1.0

    # Timestamps
    analyzed_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Queue job reference
    queue_job_id = Column(Integer, ForeignKey("queue_jobs.id"), nullable=True)

    # Relationship
    competitor = relationship("ProductCompetitor", backref="pricing_analyses")

    def __repr__(self):
        return f"<CompetitorPricingAnalysis(competitor_id={self.product_competitor_id}, model={self.pricing_model})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "product_competitor_id": self.product_competitor_id,
            "pricing_model": self.pricing_model,
            "has_free_tier": self.has_free_tier,
            "has_trial": self.has_trial,
            "trial_days": self.trial_days,
            "pricing_tiers": self.pricing_tiers,
            "has_enterprise": self.has_enterprise,
            "enterprise_contact_required": self.enterprise_contact_required,
            "source_url": self.source_url,
            "confidence": self.confidence,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
        }


class CompetitorPositioningAnalysis(Base):
    """
    Positioning and messaging analysis for a competitor.

    Captures value propositions, target audience, and key differentiators.
    """
    __tablename__ = "competitor_positioning_analysis"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_competitor_id = Column(
        Integer,
        ForeignKey("product_competitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Messaging
    tagline = Column(String(500), nullable=True)
    value_propositions = Column(JSON, nullable=True)  # ["Fast setup", "Enterprise-ready", ...]

    # Audience
    target_audience = Column(Text, nullable=True)  # Description of ideal customer
    target_company_size = Column(String(100), nullable=True)  # "SMB", "Mid-market", "Enterprise"
    target_industries = Column(JSON, nullable=True)  # ["SaaS", "Healthcare", ...]

    # Differentiation
    key_differentiators = Column(JSON, nullable=True)  # ["AI-powered", "No-code", ...]
    positioning_statement = Column(Text, nullable=True)  # Full positioning statement
    market_segment = Column(String(100), nullable=True)  # Primary market segment

    # Source tracking
    source_urls = Column(JSON, nullable=True)  # [url1, url2, ...]
    confidence = Column(Float, nullable=True)  # 0.0-1.0

    # Timestamps
    analyzed_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Queue job reference
    queue_job_id = Column(Integer, ForeignKey("queue_jobs.id"), nullable=True)

    # Relationship
    competitor = relationship("ProductCompetitor", backref="positioning_analyses")

    def __repr__(self):
        return f"<CompetitorPositioningAnalysis(competitor_id={self.product_competitor_id}, segment={self.market_segment})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "product_competitor_id": self.product_competitor_id,
            "tagline": self.tagline,
            "value_propositions": self.value_propositions,
            "target_audience": self.target_audience,
            "target_company_size": self.target_company_size,
            "target_industries": self.target_industries,
            "key_differentiators": self.key_differentiators,
            "positioning_statement": self.positioning_statement,
            "market_segment": self.market_segment,
            "source_urls": self.source_urls,
            "confidence": self.confidence,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
        }


class CompetitorChangeEvent(Base):
    """
    Tracked change events for competitors.

    Records feature launches, pricing changes, and other significant updates
    detected from release notes, blogs, and changelogs.
    """
    __tablename__ = "competitor_change_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_competitor_id = Column(
        Integer,
        ForeignKey("product_competitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Event details
    event_type = Column(String(50), nullable=False, index=True)  # "feature_launch", "pricing_change", "integration", "acquisition"
    event_title = Column(String(500), nullable=False)
    event_description = Column(Text, nullable=True)
    event_date = Column(DateTime, nullable=True)  # When the event occurred (if known)

    # Source tracking
    source_url = Column(String(500), nullable=True)
    source_type = Column(String(100), nullable=True)  # "release_notes", "blog", "changelog", "press_release"

    # Impact assessment
    impact_level = Column(String(50), nullable=True)  # "major", "minor", "patch"

    # Timestamps
    detected_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Queue job reference
    queue_job_id = Column(Integer, ForeignKey("queue_jobs.id"), nullable=True)

    # Relationship
    competitor = relationship("ProductCompetitor", backref="change_events")

    def __repr__(self):
        return f"<CompetitorChangeEvent(competitor_id={self.product_competitor_id}, type={self.event_type})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "product_competitor_id": self.product_competitor_id,
            "event_type": self.event_type,
            "event_title": self.event_title,
            "event_description": self.event_description,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "impact_level": self.impact_level,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
        }


class CompetitorMomentumAnalysis(Base):
    """
    Momentum and growth signal analysis for a competitor.

    Tracks customer wins, market expansion, and product velocity indicators.
    """
    __tablename__ = "competitor_momentum_analysis"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_competitor_id = Column(
        Integer,
        ForeignKey("product_competitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Customer Growth Signals
    # [{customer_name: "...", industry: "...", date: "...", source_url: "..."}]
    customer_wins = Column(JSON, nullable=True)
    customer_growth_trend = Column(String(50), nullable=True)  # "accelerating", "stable", "declining"
    notable_customers = Column(JSON, nullable=True)  # List of notable/enterprise customers

    # Market Expansion
    # [{market: "EMEA", date: "...", source: "..."}] - geographic or vertical
    new_markets = Column(JSON, nullable=True)
    # [{partner: "...", type: "integration", date: "...", source: "..."}]
    partnership_announcements = Column(JSON, nullable=True)

    # Product Momentum
    release_velocity = Column(String(50), nullable=True)  # "high", "medium", "low"
    major_launches_last_90_days = Column(Integer, nullable=True)

    # Social/Community Signals
    # {github_stars_trend: "rising", community_size: 5000, ...}
    community_growth_signals = Column(JSON, nullable=True)

    # Composite Score
    momentum_score = Column(Float, nullable=True)  # 0.0-1.0 composite score
    momentum_trend = Column(String(50), nullable=True)  # "rising", "stable", "declining"
    analysis_summary = Column(Text, nullable=True)

    # Confidence
    confidence = Column(Float, nullable=True)  # 0.0-1.0

    # Timestamps
    analyzed_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Queue job reference
    queue_job_id = Column(Integer, ForeignKey("queue_jobs.id"), nullable=True)

    # Relationship
    competitor = relationship("ProductCompetitor", backref="momentum_analyses")

    def __repr__(self):
        return f"<CompetitorMomentumAnalysis(competitor_id={self.product_competitor_id}, trend={self.momentum_trend})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "product_competitor_id": self.product_competitor_id,
            "customer_wins": self.customer_wins,
            "customer_growth_trend": self.customer_growth_trend,
            "notable_customers": self.notable_customers,
            "new_markets": self.new_markets,
            "partnership_announcements": self.partnership_announcements,
            "release_velocity": self.release_velocity,
            "major_launches_last_90_days": self.major_launches_last_90_days,
            "community_growth_signals": self.community_growth_signals,
            "momentum_score": self.momentum_score,
            "momentum_trend": self.momentum_trend,
            "analysis_summary": self.analysis_summary,
            "confidence": self.confidence,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
        }


class CompetitorFinancialsAnalysis(Base):
    """
    Financial analysis for a competitor.

    Tracks funding, revenue, and headcount for growth assessment.
    Only populated when data is publicly available.
    """
    __tablename__ = "competitor_financials_analysis"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_competitor_id = Column(
        Integer,
        ForeignKey("product_competitors.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Company Info
    company_type = Column(String(50), nullable=True)  # "public", "private", "startup"

    # Funding (for private companies)
    total_funding = Column(Float, nullable=True)  # Total USD raised
    # {amount: 50000000, type: "series_b", date: "2024-01-15", investors: ["A16Z", "...]}
    last_funding_round = Column(JSON, nullable=True)
    funding_stage = Column(String(50), nullable=True)  # "seed", "series_a", "series_b", etc.

    # Public Company Metrics
    market_cap = Column(Float, nullable=True)  # USD
    revenue_ttm = Column(Float, nullable=True)  # Trailing twelve months USD
    revenue_growth_yoy = Column(Float, nullable=True)  # Year over year % (-100 to 1000+)

    # Headcount (proxy for growth)
    employee_count = Column(Integer, nullable=True)
    employee_growth_yoy = Column(Float, nullable=True)  # % growth

    # Assessment
    financial_health = Column(String(50), nullable=True)  # "strong", "moderate", "weak"
    analysis_summary = Column(Text, nullable=True)

    # Data sources
    data_sources = Column(JSON, nullable=True)  # ["crunchbase", "linkedin", "sec_filings"]

    # Confidence
    confidence = Column(Float, nullable=True)  # 0.0-1.0

    # Timestamps
    analyzed_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Queue job reference
    queue_job_id = Column(Integer, ForeignKey("queue_jobs.id"), nullable=True)

    # Relationship
    competitor = relationship("ProductCompetitor", backref="financials_analyses")

    def __repr__(self):
        return f"<CompetitorFinancialsAnalysis(competitor_id={self.product_competitor_id}, health={self.financial_health})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "product_competitor_id": self.product_competitor_id,
            "company_type": self.company_type,
            "total_funding": self.total_funding,
            "last_funding_round": self.last_funding_round,
            "funding_stage": self.funding_stage,
            "market_cap": self.market_cap,
            "revenue_ttm": self.revenue_ttm,
            "revenue_growth_yoy": self.revenue_growth_yoy,
            "employee_count": self.employee_count,
            "employee_growth_yoy": self.employee_growth_yoy,
            "financial_health": self.financial_health,
            "analysis_summary": self.analysis_summary,
            "data_sources": self.data_sources,
            "confidence": self.confidence,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
        }
