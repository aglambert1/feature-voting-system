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
    job_id: Optional[str] = Field(
        default=None,
        description="Job ID this feature serves (e.g., 'j1'), linking to the product's job map"
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


class OutcomeCoverage(BaseModel):
    """Coverage of a desired outcome by our product vs competitor."""
    desired_outcome: str = Field(description="The desired outcome from the job map")
    our_coverage: Literal["full", "partial", "none"] = Field(
        description="How well our product covers this outcome"
    )
    competitor_coverage: Literal["full", "partial", "none"] = Field(
        description="How well the competitor covers this outcome"
    )


class JobFeatureAssessment(BaseModel):
    """A feature contributing to a job's satisfaction score."""
    feature_name: str = Field(description="Name of the feature")
    description: str = Field(description="What the feature does functionally")
    whose: Literal["ours", "theirs", "both"] = Field(
        description="Which product has this feature"
    )
    position: Literal["advantage", "gap", "parity", "differentiator"] = Field(
        description="Our position: advantage=we have/they don't, gap=they have/we don't, parity=both have, differentiator=unique workflow"
    )
    evidence_ids: List[int] = Field(
        default=[],
        description="IDs of evidence records that informed this assessment"
    )


class JobAssessment(BaseModel):
    """Unified per-job comparison between our product and a competitor.

    This is the core analytical unit — one per job per competitor.
    Advantages and gaps are both represented as features with different
    'position' values, not in separate structures.
    """
    job_id: str = Field(description="Job ID from the product's job map (e.g., 'j1')")
    job_statement: str = Field(description="The full job statement")
    importance: Literal["critical", "high", "medium", "low"] = Field(
        description="How important this job is to the target customer"
    )
    our_score: int = Field(ge=1, le=10, description="How well our product serves this job (1-10)")
    competitor_score: int = Field(ge=1, le=10, description="How well the competitor serves this job (1-10)")
    score_rationale: str = Field(
        description="Explanation of what drives the score difference"
    )
    features: List[JobFeatureAssessment] = Field(
        default=[],
        description="Features that contribute to the scores (both advantages and gaps)"
    )
    outcome_coverage: List[OutcomeCoverage] = Field(
        default=[],
        description="How each desired outcome is covered by both products"
    )


class EvidenceCitation(BaseModel):
    """Tracks which evidence informed a specific finding."""
    evidence_id: int = Field(description="ID of the evidence record")
    finding_type: str = Field(
        description="Type of finding: 'job_score', 'feature_assessment', 'outcome_coverage'"
    )
    finding_description: str = Field(
        description="Brief description of what this evidence informed"
    )


class FunctionalAuditOutput(BaseModel):
    """
    Complete output schema for CompetitorFunctionalAuditAgent.

    When a job map is available, includes job_assessments (the primary output).
    When no job map exists, falls back to feature-centric analysis only.
    """
    competitor_context: CompetitorContext = Field(
        description="Section 0: Competitor context summary"
    )
    functional_comparison: List[FunctionalComparison] = Field(
        description="Section 1: Functional comparison table"
    )
    gaps_deep_dive: List[GapDeepDive] = Field(
        default=[],
        description="Section 2: Deep-dive on features marked as Gap (legacy, kept for backward compat)"
    )
    technical_constraints: TechnicalConstraints = Field(
        description="Section 3: Technical constraints and requirements"
    )
    # New JTBD fields
    job_assessments: List[JobAssessment] = Field(
        default=[],
        description="Per-job unified comparison (populated when job map is available)"
    )
    evidence_citations: List[EvidenceCitation] = Field(
        default=[],
        description="Evidence records cited in the analysis"
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
    jtbd_statement: Optional[str] = Field(
        default=None,
        description="The customer job this feature serves: 'When [situation], I want to [motivation], so I can [outcome]'"
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
    job_assessments: Optional[List[JobAssessment]] = None
    evidence_citations: Optional[List[EvidenceCitation]] = None
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
