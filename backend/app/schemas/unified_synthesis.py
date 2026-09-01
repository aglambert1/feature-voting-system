"""
Pydantic schemas for the unified synthesis agent.

The UnifiedSynthesisAgent replaces both the LandscapeOpportunitySynthesizerAgent
and the OpportunitySynthesisAgent with a single Jobs-to-be-Done (JTBD) centric
synthesis step that can combine up to four signal sources:

1. Competitive intelligence (job_assessments from functional reports)
2. Customer feedback (ideas with vote counts and JTBD statements)
3. Internal feedback (win/loss + support themes with JTBD statements)
4. Evidence/research (factbase evidence items with JTBD statements)

The agent produces:
- A per-job scorecard (us vs each competitor, ranked, with investment rec)
- A feature cluster matrix organized by job (prevalence + our status)
- Unified opportunities that merge semantically equivalent signals across sources
- High-impact items (gaps to close or advantages to defend)
- Innovation whitespace + analysis summary

These schemas live in a separate module to avoid collisions with the existing
synthesis schemas while Phase 3d is still in-flight.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Job Scorecard
# =============================================================================

class JobScorecardEntry(BaseModel):
    """Per-job scorecard entry comparing our product against competitors."""
    job_id: str = Field(description="Job ID from the product's job map (e.g., 'j1')")
    job_statement: str = Field(description="The full job statement")
    importance: str = Field(
        default="medium",
        description="Job importance: critical, high, medium, or low"
    )
    our_score: int = Field(
        ge=0, le=10,
        description=(
            "How well our product serves this job, judged against the job itself "
            "rather than against competitors (1-10, 0 if unknown)"
        )
    )
    competitor_scores: Dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Map of competitor name -> score (1-10), as supporting context. Deliberately "
            "not reduced to a rank or a winner: the customer's real alternative is often a "
            "manual process or doing nothing, so a leaderboard of tracked vendors answers "
            "a narrower question than whether the job gets done."
        )
    )
    investment_recommendation: str = Field(
        description=(
            "Recommended investment level: invest_heavily, invest, defend, "
            "maintain, or deprioritize"
        )
    )
    rationale: str = Field(
        description="Why this investment recommendation, grounded in scores and evidence"
    )
    evidence_ids: List[int] = Field(
        default_factory=list,
        description="IDs of evidence records supporting this scorecard entry"
    )


# =============================================================================
# Feature Cluster Matrix (by Job)
# =============================================================================

class JobFeatureCluster(BaseModel):
    """A feature row within a job cluster, with prevalence across competitors."""
    feature_name: str = Field(description="Name of the feature")
    prevalence: str = Field(
        description=(
            "Prevalence across landscape: Table Stakes (80%+), Common (50-79%), "
            "Emerging (25-49%), or Frontier (<25%)"
        )
    )
    our_status: str = Field(
        description="Our status: Have, Gap, or Partial"
    )
    competitors_with_feature: List[str] = Field(
        default_factory=list,
        description="Names of competitors that have this feature"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes about this feature cluster"
    )


class JobFeatureClusterMatrix(BaseModel):
    """Feature cluster matrix organized under a specific job."""
    job_id: str = Field(description="Job ID from the product's job map")
    job_statement: str = Field(description="The full job statement")
    features: List[JobFeatureCluster] = Field(
        default_factory=list,
        description="Features contributing to this job, with prevalence data"
    )


# =============================================================================
# High-Impact Items (gaps to close or advantages to defend)
# =============================================================================

class HighImpactItem(BaseModel):
    """A high-impact gap to close or advantage to defend."""
    type: str = Field(description="Either 'gap' or 'advantage'")
    job_id: Optional[str] = Field(
        default=None,
        description="Job ID this item relates to, if any"
    )
    rank: int = Field(
        ge=1, le=10,
        description="Rank 1-10, with 1 being highest priority"
    )
    title: str = Field(description="Short, action-oriented title")
    description: str = Field(description="What the item is and what it entails")
    market_gravity: str = Field(
        description="Why this matters (demand, competitive pressure, etc.)"
    )
    competitors: List[str] = Field(
        default_factory=list,
        description="Competitors involved in this gap/advantage"
    )


# =============================================================================
# Unified Opportunity (feeds SynthesizedOpportunity records)
# =============================================================================

class UnifiedOpportunity(BaseModel):
    """
    An opportunity produced by unified synthesis.

    Semantically equivalent signals from different sources are merged into a
    single opportunity with source_count reflecting how many sources agree.
    """
    opportunity_name: str = Field(description="Clear, actionable opportunity name")
    opportunity_summary: str = Field(
        description="Brief explanation of why this opportunity is valuable"
    )
    priority_score: float = Field(
        ge=0, le=100,
        description="Priority score from 0-100"
    )
    source_count: int = Field(
        ge=1, le=4,
        description="Number of sources that contributed to this opportunity"
    )
    sources: List[str] = Field(
        description=(
            "Source tags: any of 'competitive', 'customer', 'internal', "
            "'evidence_research'"
        )
    )
    job_id_key: Optional[str] = Field(
        default=None,
        description="Job ID this opportunity maps to, if job map is available"
    )
    job_satisfaction_delta: Optional[float] = Field(
        default=None,
        description="Projected improvement to our job score if this ships (points on the 1-10 scale)"
    )
    investment_tier: Optional[str] = Field(
        default=None,
        description="Investment tier: invest_heavily, invest, defend, maintain, or deprioritize"
    )

    # Source-specific evidence blobs. Shapes mirror the existing
    # SynthesizedOpportunityOutput evidence structures so downstream consumers
    # can keep using the same writer code.
    competitive_evidence: Optional[dict] = Field(
        default=None,
        description="Competitive evidence blob (feature_name, prevalence, competitors, ...)"
    )
    customer_evidence: Optional[dict] = Field(
        default=None,
        description="Customer evidence blob (idea_id, idea_title, board_votes, external_votes, external_source, ...)"
    )
    internal_evidence: Optional[dict] = Field(
        default=None,
        description="Internal evidence blob (winloss, support)"
    )
    evidence_signals: Optional[dict] = Field(
        default=None,
        description="Evidence/research blob (items: [...])"
    )

    recommended_action: str = Field(
        description="Recommended action: high_priority, investigate, monitor, or quick_win"
    )
    feature_keywords: List[str] = Field(
        default_factory=list,
        description="Keywords for matching this opportunity against other systems"
    )
    jtbd_statement: Optional[str] = Field(
        default=None,
        description=(
            "Unified JTBD: 'When [situation], I want to [motivation], "
            "so I can [outcome]'"
        )
    )


# =============================================================================
# Agent Output
# =============================================================================

class UnifiedSynthesisOutput(BaseModel):
    """Complete output of the UnifiedSynthesisAgent."""
    job_scorecard: List[JobScorecardEntry] = Field(
        default_factory=list,
        description="Per-job scorecard. Empty when no job map is provided."
    )
    feature_cluster_matrix: List[JobFeatureClusterMatrix] = Field(
        default_factory=list,
        description=(
            "Feature cluster matrix grouped by job. Empty for self-assessment "
            "mode with no competitors."
        )
    )
    opportunities: List[UnifiedOpportunity] = Field(
        default_factory=list,
        description="Prioritized synthesized opportunities, sorted by priority_score"
    )
    high_impact_items: List[HighImpactItem] = Field(
        default_factory=list,
        description="High-impact gaps to close or advantages to defend"
    )
    innovation_whitespace: Optional[str] = Field(
        default=None,
        description="Persistent unsolved problem across the landscape"
    )
    analysis_summary: Optional[str] = Field(
        default=None,
        description="Short narrative summary of the synthesis findings"
    )
