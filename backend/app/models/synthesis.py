"""
Synthesis models for multi-source opportunity synthesis.

This module defines database models for:
1. SynthesisRun - Tracks a synthesis run combining multiple sources (legacy
   placeholder kept for SynthesizedOpportunity FK compatibility)
2. SynthesizedOpportunity - Opportunities identified from cross-source analysis
3. SynthesisConfig - Per-product configuration for the unified synthesis agent
4. SynthesisReport - Unified synthesis report (Phase 3)

These models support the unified synthesis agent which combines:
- Competitive intelligence (from competitor functional reports)
- Customer feedback (from voting system)
- Internal feedback (from win/loss and support themes)
- Evidence research (from the product factbase)
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    JSON, Boolean, Float, Enum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class SynthesisStatus(str, enum.Enum):
    """Status of a synthesis run."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceType(str, enum.Enum):
    """Types of sources that can contribute to synthesis."""
    COMPETITIVE = "competitive"
    CUSTOMER = "customer"
    INTERNAL = "internal"
    EVIDENCE_RESEARCH = "evidence_research"


class SynthesisRun(Base):
    """
    Tracks a synthesis run that combines multiple data sources.

    Each run captures a snapshot of available data from:
    - Competitive: CompetitorFunctionalReports (per-competitor audits)
    - Customer: Ideas with votes
    - Internal: WinLossThemes and SupportThemes
    - Evidence: Evidence records from the product factbase

    The unified synthesis agent processes these sources to
    identify intersections and generate prioritized opportunities.
    """
    __tablename__ = "synthesis_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(
        Integer,
        ForeignKey("ci_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Run status
    status = Column(
        String(20),
        nullable=False,
        default="pending"
    )  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)

    # Source data references
    # Stores IDs/counts of data used for this synthesis
    source_snapshot = Column(JSON, nullable=True)
    # Example: {
    #   "landscape_report_id": 5,
    #   "competitive_opportunities_count": 12,
    #   "ideas_count": 45,
    #   "ideas_total_votes": 892,
    #   "internal_import_id": 3,
    #   "winloss_themes_count": 8,
    #   "support_themes_count": 10
    # }

    # Sources available for this run
    sources_used = Column(JSON, nullable=True)
    # Example: ["competitive", "customer", "internal"]

    # Summary statistics from synthesis
    summary_stats = Column(JSON, nullable=True)
    # Example: {
    #   "three_way_matches": 2,
    #   "two_way_matches": 5,
    #   "single_source": 8,
    #   "total_opportunities": 15
    # }

    # Analysis summary from agent
    analysis_summary = Column(Text, nullable=True)

    # Job tracking
    job_uuid = Column(String(36), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    opportunities = relationship(
        "SynthesizedOpportunity",
        back_populates="synthesis_run",
        cascade="all, delete-orphan",
        order_by="desc(SynthesizedOpportunity.priority_score)"
    )
    product = relationship("CIProduct", backref="synthesis_runs")

    def __repr__(self):
        return f"<SynthesisRun(id={self.id}, product_id={self.product_id}, status={self.status})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "status": self.status,
            "error_message": self.error_message,
            "source_snapshot": self.source_snapshot,
            "sources_used": self.sources_used,
            "summary_stats": self.summary_stats,
            "analysis_summary": self.analysis_summary,
            "job_uuid": self.job_uuid,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "opportunity_count": len(self.opportunities) if self.opportunities else 0,
        }


class SynthesizedOpportunity(Base):
    """
    An opportunity identified from cross-source synthesis.

    Each opportunity represents a feature or capability need that
    was identified by analyzing the intersection of:
    - Competitive gaps (features competitors have that we don't)
    - Customer requests (highly voted ideas)
    - Internal signals (win/loss themes, support themes)

    Opportunities are scored based on the number and strength
    of signals from each source.
    """
    __tablename__ = "synthesized_opportunities"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    synthesis_run_id = Column(
        Integer,
        ForeignKey("synthesis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    product_id = Column(
        Integer,
        ForeignKey("ci_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Opportunity identification
    opportunity_name = Column(String(255), nullable=False)
    opportunity_summary = Column(Text, nullable=True)

    # Priority scoring (0-100)
    priority_score = Column(Float, nullable=False, default=0.0)

    # Source count (1-4: competitive, customer, internal, evidence/research)
    source_count = Column(Integer, nullable=False, default=1)

    # Which sources contributed to this opportunity
    sources = Column(JSON, nullable=True)
    # Example: ["competitive", "customer", "internal", "evidence_research"]

    # Evidence from each source
    competitive_evidence = Column(JSON, nullable=True)
    # Example: {
    #   "feature_name": "Time Tracking",
    #   "prevalence": "Table Stakes",
    #   "competitors": ["Competitor A", "Competitor B", "Competitor C"],
    #   "competitor_count": 4,
    #   "our_status": "Gap"
    # }

    customer_evidence = Column(JSON, nullable=True)
    # Example: {
    #   "idea_id": 42,
    #   "idea_title": "Add time tracking feature",
    #   "vote_count": 85,
    #   "status": "under_review"
    # }

    internal_evidence = Column(JSON, nullable=True)
    # Example: {
    #   "winloss": {
    #     "theme_id": 5,
    #     "theme_name": "Time Tracking Capability",
    #     "outcome": "lost",
    #     "deal_count": 8,
    #     "total_value": 340000,
    #     "competitor_correlation": "Competitor A"
    #   },
    #   "support": {
    #     "theme_id": 12,
    #     "theme_name": "Time Tracking Requests",
    #     "ticket_count": 23,
    #     "category": "feature_request"
    #   }
    # }

    # Evidence/research from factbase (4th source)
    evidence_signals = Column(JSON, nullable=True)
    # Example: {
    #   "evidence_ids": [1, 5, 12],
    #   "items": [
    #     {"evidence_id": 1, "title": "Asana launches AI triage", "evidence_type": "competitive_intel", "source_url": "..."},
    #     {"evidence_id": 5, "title": "Customer interview - Acme", "evidence_type": "customer_interview"}
    #   ]
    # }

    # Recommended action from synthesis
    recommended_action = Column(String(100), nullable=True)
    # Example: "high_priority", "monitor", "investigate", "quick_win"

    # Keywords for matching (aggregated from all sources)
    feature_keywords = Column(JSON, nullable=True)

    # Embedding for semantic matching (stored as JSON array)
    embedding = Column(JSON, nullable=True)

    # Jobs-to-be-Done extraction
    jtbd_statement = Column(Text, nullable=True)  # Unified JTBD synthesized across all contributing sources
    jtbd_embedding = Column(JSON, nullable=True)  # 1024-dim Voyage AI embedding for cross-opportunity clustering

    # Link to created idea (if user creates one from this opportunity)
    linked_idea_id = Column(
        Integer,
        ForeignKey("ideas.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Phase 3: link to unified SynthesisReport
    # Nullable for backward compatibility with records created via SynthesisRun
    synthesis_report_id = Column(
        Integer,
        ForeignKey("synthesis_reports.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    # JTBD job linkage (resolved via ProductJob.job_id_key during synthesis)
    job_id_key = Column(String(50), nullable=True)

    # Investment tier from the unified scorecard
    # One of: "invest_heavily", "invest", "defend", "maintain", "deprioritize"
    investment_tier = Column(String(50), nullable=True)

    # Projected satisfaction score improvement if this opportunity ships
    job_satisfaction_delta = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    synthesis_run = relationship(
        "SynthesisRun",
        back_populates="opportunities"
    )
    synthesis_report = relationship(
        "SynthesisReport",
        backref="opportunities_list"
    )
    product = relationship("CIProduct", backref="synthesized_opportunities")
    linked_idea = relationship("Idea", backref="source_opportunities")

    def __repr__(self):
        return f"<SynthesizedOpportunity(id={self.id}, name={self.opportunity_name}, score={self.priority_score})>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "synthesis_run_id": self.synthesis_run_id,
            "product_id": self.product_id,
            "opportunity_name": self.opportunity_name,
            "opportunity_summary": self.opportunity_summary,
            "priority_score": self.priority_score,
            "source_count": self.source_count,
            "sources": self.sources,
            "competitive_evidence": self.competitive_evidence,
            "customer_evidence": self.customer_evidence,
            "internal_evidence": self.internal_evidence,
            "evidence_signals": self.evidence_signals,
            "recommended_action": self.recommended_action,
            "feature_keywords": self.feature_keywords,
            "linked_idea_id": self.linked_idea_id,
            "jtbd_statement": self.jtbd_statement,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def get_match_type_label(self) -> str:
        """Get human-readable match type label."""
        if self.source_count >= 4:
            return "Four-Way Match"
        elif self.source_count == 3:
            return "Three-Way Match"
        elif self.source_count == 2:
            return "Two-Way Match"
        else:
            return "Single Source"

    def get_export_dict(self) -> dict:
        """Get dictionary format suitable for export."""
        return {
            "name": self.opportunity_name,
            "summary": self.opportunity_summary,
            "priority_score": self.priority_score,
            "match_type": self.get_match_type_label(),
            "sources": self.sources,
            "evidence": {
                "competitive": self.competitive_evidence,
                "customer": self.customer_evidence,
                "internal": self.internal_evidence,
                "evidence_research": self.evidence_signals,
            },
            "recommended_action": self.recommended_action,
            "keywords": self.feature_keywords,
        }


class SynthesisConfig(Base):
    """Per-product synthesis configuration.

    Controls which source types are included in synthesis and idea
    auto-generation behavior. Competitor inclusion is tracked on
    ProductCompetitor.synthesis_included, not here.
    """
    __tablename__ = "synthesis_configs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(
        Integer,
        ForeignKey("ci_products.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Which source types to include
    # Default: ["competitive"]; any combo of competitive/customer/internal/evidence
    included_source_types = Column(JSON, nullable=False, default=list)

    # Idea auto-generation
    auto_generate_ideas = Column(Boolean, nullable=False, default=True)
    idea_priority_threshold = Column(Float, nullable=False, default=0.7)

    # Product-specific scoring overrides (merges with scoring_defaults.py)
    scoring_weight_overrides = Column(JSON, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    product = relationship("CIProduct", backref="synthesis_config")

    def __repr__(self):
        return (
            f"<SynthesisConfig(product_id={self.product_id}, "
            f"sources={self.included_source_types})>"
        )


class SynthesisReport(Base):
    """Unified synthesis report.

    Produced by the unified synthesis agent. Handles:
    - Competitive mode (only competitor audits + competitor-linked evidence)
    - Multi-source mode (competitors + customer + internal + evidence)
    - Self-assessment mode (no competitors; scoring uses customer/internal/evidence)
    """
    __tablename__ = "synthesis_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(
        Integer,
        ForeignKey("ci_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_version = Column(Integer, nullable=False, default=1)

    # Which sources were included in this run
    # Example: ["competitive", "customer", "internal", "evidence"]
    included_source_types = Column(JSON, nullable=False)

    # Per-job scorecard (our_score, competitor_scores, best_in_class, investment_rec)
    # [{job_id, job_statement, importance, our_score, competitor_scores: {name: score},
    #   best_in_class, our_rank, total_ranked, investment_recommendation, rationale,
    #   evidence_ids}]
    job_scorecard = Column(JSON, nullable=True)

    # Feature cluster matrix, organized by job (null if no competitors)
    # {job_id: {features: [{feature_name, prevalence, our_status,
    #                       competitors_with_feature, notes}]}}
    feature_cluster_matrix = Column(JSON, nullable=True)

    # Unified opportunity list -- these spawn SynthesizedOpportunity rows
    # (same structure as before, now with job_id_key linkage)
    opportunities = Column(JSON, nullable=True)

    # High-impact items (gaps to close AND advantages to defend)
    # [{type: "gap"|"advantage", job_id, rank, description, market_gravity, competitors}]
    high_impact_items = Column(JSON, nullable=True)

    # Innovation whitespace narrative
    innovation_whitespace = Column(Text, nullable=True)
    analysis_summary = Column(Text, nullable=True)

    # Source statistics (counts per input source)
    # {competitor_count, competitor_report_count, idea_count, winloss_count,
    #  support_count, evidence_count}
    source_stats = Column(JSON, nullable=True)

    # Which competitors were in this run (may be empty for self-assessment)
    included_competitor_ids = Column(JSON, nullable=True)
    source_competitor_report_ids = Column(JSON, nullable=True)

    # Change detection from previous version
    changes_from_previous = Column(JSON, nullable=True)

    # Markdown content for display/export
    report_content_md = Column(Text, nullable=True)

    # Job tracking
    queue_job_id = Column(Integer, ForeignKey("queue_jobs.id"), nullable=True)
    generated_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    product = relationship("CIProduct", backref="synthesis_reports")

    def __repr__(self):
        return (
            f"<SynthesisReport(id={self.id}, product_id={self.product_id}, "
            f"v{self.report_version})>"
        )
