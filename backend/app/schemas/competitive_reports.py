"""
Pydantic schemas for competitive report agents.

These schemas define the structured output format for:
- CompetitorFunctionalAuditAgent
- LandscapeOpportunitySynthesizerAgent
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# =============================================================================
# Functional Audit Agent Output Schemas
# =============================================================================

class CompetitorContext(BaseModel):
    """Section 0: Competitor context summary."""
    positioning: str = Field(
        description="Their hero message and how they describe themselves"
    )
    core_differentiation: str = Field(
        description="What makes them unique - their key value proposition"
    )
    target_customer: str = Field(
        description="Their ideal customer profile (ICP)"
    )
    key_features: List[str] = Field(
        default=[],
        description="Top 5 unique or core features"
    )


class FunctionalComparison(BaseModel):
    """A single row in the functional comparison table."""
    feature_category: str = Field(
        description="Category of the feature (e.g., 'Analytics', 'Integrations')"
    )
    competitor_feature_name: str = Field(
        description="Name of the feature as the competitor calls it"
    )
    functional_description: str = Field(
        description="What the feature actually does (functional, not marketing)"
    )
    mapping_status: Literal["Parity", "Advantage", "Gap", "Differentiator"] = Field(
        description="Parity=both have, Advantage=we have/they don't, Gap=they have/we don't, Differentiator=unique workflow"
    )


class GapDeepDive(BaseModel):
    """Deep-dive on a feature gap (Section 2)."""
    feature_name: str = Field(
        description="Name of the gap feature"
    )
    user_problem: str = Field(
        description="What specific pain point does this feature solve?"
    )
    evidence: str = Field(
        description="Quote or description from documentation/reviews proving value"
    )


class TechnicalConstraints(BaseModel):
    """Section 3: Technical constraints and requirements."""
    integrations: List[str] = Field(
        default=[],
        description="Key integrations (e.g., 'Salesforce', 'Slack')"
    )
    api_capabilities: Optional[str] = Field(
        default=None,
        description="API availability and capabilities"
    )
    platform_requirements: Optional[str] = Field(
        default=None,
        description="Platform requirements (e.g., 'Mobile only', 'Web app')"
    )
    additional_notes: Optional[str] = Field(
        default=None,
        description="Any other technical constraints or notes"
    )


class FunctionalAuditOutput(BaseModel):
    """
    Complete output schema for CompetitorFunctionalAuditAgent.

    Sections:
    0. Competitor context
    1. Functional comparison table
    2. Deep-dive on gaps
    3. Technical constraints
    """
    competitor_context: CompetitorContext = Field(
        description="Section 0: Competitor context summary"
    )
    functional_comparison: List[FunctionalComparison] = Field(
        description="Section 1: Functional comparison table"
    )
    gaps_deep_dive: List[GapDeepDive] = Field(
        default=[],
        description="Section 2: Deep-dive on features marked as Gap"
    )
    technical_constraints: TechnicalConstraints = Field(
        description="Section 3: Technical constraints and requirements"
    )


# =============================================================================
# Landscape Opportunity Synthesizer Output Schemas
# =============================================================================

class FeatureClusterEntry(BaseModel):
    """A single row in the feature cluster matrix (Section 1)."""
    feature_category: str = Field(
        description="Category or name of the feature"
    )
    prevalence: Literal["Table Stakes", "Common", "Emerging", "Frontier"] = Field(
        description="Table Stakes=80%+, Common=50-79%, Emerging=25-49%, Frontier=<25%"
    )
    our_status: Literal["Have", "Gap", "Partial"] = Field(
        description="Have=we have it, Gap=we don't, Partial=partially implemented"
    )
    competitors_with_feature: List[str] = Field(
        description="Names of competitors that have this feature"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes about this feature cluster"
    )


class FeatureOpportunity(BaseModel):
    """
    A feature opportunity for export to voting/roadmap systems (Section 2).

    This schema is designed to be portable and system-agnostic.
    """
    feature_name: str = Field(
        description="Concise name of the feature"
    )
    summary: str = Field(
        description="1-2 sentence description of what the feature does"
    )
    user_value: str = Field(
        description="The primary benefit to the customer"
    )
    market_context: str = Field(
        description="Which competitors have it and whether Table Stakes or Innovation"
    )
    priority_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Relative priority score (0.0-1.0)"
    )
    competitors_with_feature: List[str] = Field(
        default=[],
        description="List of competitor names that have this feature"
    )
    source_evidence: List[str] = Field(
        default=[],
        description="Supporting evidence (quotes, reviews, etc.)"
    )


class HighImpactGap(BaseModel):
    """A high-impact gap feature (Section 3)."""
    rank: int = Field(
        ge=1,
        le=10,
        description="Rank 1-10, with 1 being highest priority"
    )
    feature_name: str = Field(
        description="Name of the gap feature"
    )
    market_gravity: str = Field(
        description="Why this has high market gravity (demand, competition, etc.)"
    )
    competitors_with_feature: List[str] = Field(
        description="Which competitors have this feature"
    )
    user_demand_evidence: str = Field(
        description="Evidence of user demand (reviews, requests, etc.)"
    )


class LandscapeSynthesisOutput(BaseModel):
    """
    Complete output schema for LandscapeOpportunitySynthesizerAgent.

    Sections:
    1. Feature cluster matrix
    2. Feature opportunities (JSON export)
    3. High-impact gaps
    """
    feature_cluster_matrix: List[FeatureClusterEntry] = Field(
        description="Section 1: Feature cluster matrix showing prevalence"
    )
    feature_opportunities: List[FeatureOpportunity] = Field(
        description="Section 2: Feature opportunities for voting system export"
    )
    high_impact_gaps: List[HighImpactGap] = Field(
        default=[],
        description="Section 3: Top high-impact gaps with market gravity"
    )
    innovation_whitespace: Optional[str] = Field(
        default=None,
        description="Persistent unsolved problem found across competitors"
    )
    analysis_summary: Optional[str] = Field(
        default=None,
        description="Brief summary of the landscape analysis"
    )


# =============================================================================
# API Response Schemas
# =============================================================================

class FunctionalReportResponse(BaseModel):
    """API response schema for a competitor functional report."""
    id: int
    product_competitor_id: int
    product_id: int
    competitor_name: Optional[str] = None
    report_version: int
    report_content_md: Optional[str] = None
    competitor_context: Optional[CompetitorContext] = None
    functional_comparison: Optional[List[FunctionalComparison]] = None
    gaps_deep_dive: Optional[List[GapDeepDive]] = None
    technical_constraints: Optional[TechnicalConstraints] = None
    generated_at: Optional[str] = None
    queue_job_id: Optional[int] = None


class LandscapeReportResponse(BaseModel):
    """API response schema for a landscape opportunity report."""
    id: int
    product_id: int
    report_version: int
    report_content_md: Optional[str] = None
    feature_cluster_matrix: Optional[List[FeatureClusterEntry]] = None
    feature_opportunities: Optional[List[FeatureOpportunity]] = None
    high_impact_gaps: Optional[List[HighImpactGap]] = None
    source_competitor_report_ids: Optional[List[int]] = None
    source_competitor_names: Optional[List[str]] = None
    generated_at: Optional[str] = None
    queue_job_id: Optional[int] = None


class FeatureOpportunitiesExport(BaseModel):
    """Portable export format for feature opportunities."""
    version: str = "1.0"
    generated_at: str
    product_id: int
    product_name: Optional[str] = None
    feature_ideas: List[FeatureOpportunity]
    metadata: dict = Field(default_factory=dict)
