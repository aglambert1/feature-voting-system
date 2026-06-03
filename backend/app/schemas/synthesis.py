"""
Pydantic schemas for opportunity synthesis.

These schemas define:
- Synthesis run tracking and status
- Synthesized opportunity structure with evidence from each source
- API request/response models
- Export formats
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Evidence Schemas (evidence from each source)
# =============================================================================

class CompetitiveEvidence(BaseModel):
    """Evidence from competitive intelligence."""
    feature_name: str = Field(description="Name of the competitive feature")
    prevalence: Optional[str] = Field(
        default=None,
        description="Table Stakes, Emerging, or Differentiator"
    )
    competitors: List[str] = Field(
        default=[],
        description="List of competitors with this feature"
    )
    competitor_count: int = Field(
        default=0,
        description="Number of competitors with this feature"
    )
    our_status: Optional[str] = Field(
        default=None,
        description="Our status: Gap, Parity, or Advantage"
    )
    priority_score: Optional[float] = Field(
        default=None,
        description="Priority score from landscape analysis"
    )


class CustomerEvidence(BaseModel):
    """Evidence from customer feedback (voting system)."""
    idea_id: int = Field(description="ID of the related idea")
    idea_title: str = Field(description="Title of the idea")
    vote_count: int = Field(description="Number of votes on the idea")
    status: Optional[str] = Field(
        default=None,
        description="Idea status (submitted, under_review, etc.)"
    )
    submitted_at: Optional[datetime] = Field(
        default=None,
        description="When the idea was submitted"
    )


class WinLossEvidence(BaseModel):
    """Evidence from win/loss analysis."""
    theme_id: int = Field(description="ID of the win/loss theme")
    theme_name: str = Field(description="Name of the theme")
    outcome: str = Field(description="won, lost, or both")
    deal_count: int = Field(description="Number of deals")
    total_value: float = Field(description="Total deal value")
    competitor_correlation: Optional[str] = Field(
        default=None,
        description="Most correlated competitor"
    )


class SupportEvidence(BaseModel):
    """Evidence from support ticket themes."""
    theme_id: int = Field(description="ID of the support theme")
    theme_name: str = Field(description="Name of the theme")
    ticket_count: int = Field(description="Number of tickets")
    category: str = Field(description="Theme category")
    urgency_indicator: Optional[str] = Field(
        default=None,
        description="high, medium, or low"
    )


class InternalEvidence(BaseModel):
    """Combined internal evidence (win/loss + support)."""
    winloss: Optional[WinLossEvidence] = None
    support: Optional[SupportEvidence] = None


class EvidenceResearchItem(BaseModel):
    """A single factbase evidence item contributing to an opportunity."""
    evidence_id: int = Field(description="ID of the evidence record")
    title: str = Field(description="Evidence title")
    evidence_type: str = Field(description="Type of evidence")
    source_url: Optional[str] = Field(default=None, description="Source URL if available")
    source_description: Optional[str] = Field(default=None, description="Source description")
    relevance: Optional[str] = Field(
        default=None,
        description="Brief explanation of how this evidence relates to the opportunity"
    )


class EvidenceResearchSignals(BaseModel):
    """Evidence/research from the product factbase (4th source)."""
    items: List[EvidenceResearchItem] = Field(
        default=[], description="Evidence items supporting this opportunity"
    )


# =============================================================================
# Agent Output Schema
# =============================================================================

class SynthesizedOpportunityOutput(BaseModel):
    """
    Output schema for a single synthesized opportunity from the agent.
    """
    opportunity_name: str = Field(
        description="Clear, actionable name for the opportunity"
    )
    opportunity_summary: str = Field(
        description="Brief explanation of why this opportunity is valuable"
    )
    priority_score: float = Field(
        ge=0,
        le=100,
        description="Priority score from 0-100"
    )
    source_count: int = Field(
        ge=1,
        le=4,
        description="Number of sources contributing (1-4)"
    )
    sources: List[Literal["competitive", "customer", "internal", "evidence_research"]] = Field(
        description="Which sources contributed to this opportunity"
    )
    competitive_evidence: Optional[CompetitiveEvidence] = None
    customer_evidence: Optional[CustomerEvidence] = None
    internal_evidence: Optional[InternalEvidence] = None
    evidence_signals: Optional[EvidenceResearchSignals] = None
    recommended_action: str = Field(
        description="Recommended action: high_priority, monitor, investigate, quick_win"
    )
    feature_keywords: List[str] = Field(
        default=[],
        description="Keywords for this opportunity"
    )
    jtbd_statement: Optional[str] = Field(
        default=None,
        description="Unified JTBD synthesizing the customer job across all contributing sources: 'When [situation], I want to [motivation], so I can [outcome]'"
    )


class OpportunitySynthesisOutput(BaseModel):
    """
    Complete output schema for Opportunity Synthesis Agent.
    """
    opportunities: List[SynthesizedOpportunityOutput] = Field(
        description="List of synthesized opportunities, sorted by priority"
    )
    analysis_summary: str = Field(
        description="Brief summary of synthesis findings"
    )
    source_stats: Dict[str, Any] = Field(
        description="Statistics about sources used"
    )


# =============================================================================
# API Request/Response Schemas
# =============================================================================

class SynthesisRunCreate(BaseModel):
    """Request schema for creating a synthesis run."""
    pass  # No required fields - synthesis uses latest available data


class SourceSnapshot(BaseModel):
    """Snapshot of source data used for synthesis."""
    landscape_report_id: Optional[int] = None
    competitive_opportunities_count: int = 0
    ideas_count: int = 0
    ideas_total_votes: int = 0
    internal_import_id: Optional[int] = None
    winloss_themes_count: int = 0
    support_themes_count: int = 0


class SummaryStats(BaseModel):
    """Summary statistics from synthesis."""
    four_way_matches: int = 0
    three_way_matches: int = 0
    two_way_matches: int = 0
    single_source: int = 0
    total_opportunities: int = 0


class SynthesisRunResponse(BaseModel):
    """Response schema for synthesis run."""
    id: int
    product_id: int
    status: str
    error_message: Optional[str] = None
    source_snapshot: Optional[SourceSnapshot] = None
    sources_used: List[str] = []
    summary_stats: Optional[SummaryStats] = None
    analysis_summary: Optional[str] = None
    job_uuid: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    opportunity_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class SynthesizedOpportunityResponse(BaseModel):
    """Response schema for a synthesized opportunity."""
    id: int
    synthesis_run_id: int
    product_id: int
    opportunity_name: str
    opportunity_summary: Optional[str] = None
    priority_score: float
    source_count: int
    sources: List[str]
    competitive_evidence: Optional[Dict[str, Any]] = None
    customer_evidence: Optional[Dict[str, Any]] = None
    internal_evidence: Optional[Dict[str, Any]] = None
    evidence_signals: Optional[Dict[str, Any]] = None
    recommended_action: Optional[str] = None
    feature_keywords: List[str] = []
    linked_idea_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SynthesisResultsResponse(BaseModel):
    """Full synthesis results including run info and opportunities."""
    run: SynthesisRunResponse
    opportunities: List[SynthesizedOpportunityResponse]


class SynthesisSourcesAvailable(BaseModel):
    """Available sources for synthesis."""
    competitive: bool = False
    competitive_detail: Optional[str] = None
    customer: bool = False
    customer_detail: Optional[str] = None
    internal: bool = False
    internal_detail: Optional[str] = None
    evidence: bool = False
    evidence_detail: Optional[str] = None


class SynthesisStatusResponse(BaseModel):
    """Status check response showing available sources."""
    product_id: int
    sources_available: SynthesisSourcesAvailable
    has_previous_run: bool
    previous_run: Optional[SynthesisRunResponse] = None


# =============================================================================
# Export Schemas
# =============================================================================

class OpportunityExport(BaseModel):
    """Export format for a single opportunity."""
    name: str
    summary: Optional[str]
    priority_score: float
    match_type: str
    sources: List[str]
    evidence: Dict[str, Any]
    recommended_action: Optional[str]
    keywords: List[str]


class SynthesisExportResponse(BaseModel):
    """Export format for synthesis results."""
    version: str = "1.0"
    export_format: Literal["json", "csv"]
    generated_at: datetime
    product_id: int
    product_name: Optional[str] = None
    synthesis_run_id: int
    opportunities: List[OpportunityExport]
    metadata: Dict[str, Any]
