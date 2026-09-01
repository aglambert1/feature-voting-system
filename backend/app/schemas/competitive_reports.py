"""
Pydantic schemas for competitive report agents.

These schemas define the structured output format for:
- CompetitorFunctionalAuditAgent

Landscape-synthesis schemas were removed in Phase 4b; cross-competitor
synthesis now uses app.schemas.unified_synthesis.
"""

from typing import List, Literal, Optional
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
    our_coverage: str = Field(
        default="none",
        description="How well our product covers this outcome: full, partial, or none"
    )
    competitor_coverage: str = Field(
        default="none",
        description="How well the competitor covers this outcome: full, partial, or none"
    )


class JobFeatureAssessment(BaseModel):
    """A feature contributing to a job's satisfaction score."""
    feature_name: str = Field(description="Name of the feature")
    description: str = Field(default="", description="What the feature does functionally")
    whose: str = Field(
        default="theirs",
        description="Which product has this feature: ours, theirs, or both"
    )
    position: str = Field(
        default="gap",
        description="Our position: advantage (we have/they don't), gap (they have/we don't), parity (both have), or differentiator (unique workflow)"
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
    importance: str = Field(
        default="medium",
        description="How important this job is: critical, high, medium, or low"
    )
    competitor_score: int = Field(ge=0, le=10, description="How well the competitor serves this job (1-10, 0 if unknown)")
    score_rationale: str = Field(
        description="Explanation of what drives the score difference"
    )
    confidence: str = Field(
        default="medium",
        description="Your confidence in this assessment: high, medium, or low. Use low when the competitor's public material is thin or ambiguous on this job."
    )
    features: List[JobFeatureAssessment] = Field(
        default=[],
        description="Features that contribute to the scores (both advantages and gaps)"
    )
    outcome_coverage: List[OutcomeCoverage] = Field(
        default=[],
        description="How each desired outcome is covered by both products"
    )


class StoredJobAssessment(JobAssessment):
    """A job assessment as persisted, with system-derived and human review state.

    `JobAssessment` is the contract the agent fills in. These extra fields are
    added after the agent returns and are never emitted by the model:

    - `our_score` is joined in from the product's self-assessment, with
      `self_assessment_version` recording which one. An audit scores the competitor
      only — it has no standing to score us, and letting each audit do so is what
      allowed the same job to carry a different "our" score in every report.
    - `system_position` is derived from our joined score and the audit's competitor
      score (see `app.utils.job_position`) and is the stable value change detection
      compares. It is recomputed on every run, and is `unknown` until a
      self-assessment exists — position needs both sides.
    - `human_position` is a PM's override. It is authoritative for display and
      is carried forward across re-audits so a new run never silently reverts
      it. Change detection ignores it — a human disagreeing with the model is
      not a competitor changing.

    Review is optional. An assessment nobody has reviewed keeps
    `human_position` as None, which is a normal state: a PM may accept the
    system levels without reviewing them.
    """
    our_score: Optional[int] = Field(
        default=None,
        description="Our score for this job, joined from the latest self-assessment"
    )
    self_assessment_version: Optional[int] = Field(
        default=None,
        description="Which self-assessment our_score came from"
    )
    system_position: Optional[str] = Field(
        default=None,
        description="Derived from the score bands: advantage, gap, parity, or unknown"
    )
    human_position: Optional[str] = Field(
        default=None,
        description="PM override of the system position. None means unreviewed or agreed."
    )
    reviewed_at: Optional[str] = Field(
        default=None,
        description="When a PM confirmed or overrode this assessment"
    )
    reviewed_by: Optional[int] = Field(
        default=None,
        description="User id of the PM who reviewed this assessment"
    )
    reviewed_job_statement: Optional[str] = Field(
        default=None,
        description="The job statement as worded when the review was made — the basis the override was judged against"
    )
    review_stale: bool = Field(
        default=False,
        description="True when the job has been restated since the override was made, so the override may no longer apply. Sticky until reviewed again."
    )


class UnmappedCapability(BaseModel):
    """A competitor capability that fits no job in our map.

    The job map is generated from our own product description, so it is blind by
    construction to jobs we never addressed — which is exactly where opportunity lives.
    A competitor serving a job our map doesn't contain is evidence the map is
    incomplete, and it arrives free with an audit we were running anyway.

    Recording these rather than discarding them turns every audit into a passive source
    of job discovery, independent of our own product copy.
    """
    capability: str = Field(description="What the competitor does, in functional terms")
    why_unmapped: str = Field(
        default="",
        description="Why no existing job covers it — the closest job and what it misses"
    )
    suggested_job_statement: str = Field(
        default="",
        description=(
            "A candidate job statement in 'When [situation], I want to [action], so I can "
            "[outcome]' form. A proposal for a human to accept, edit, or reject — never "
            "added to the map automatically."
        )
    )


class SelfJobAssessment(BaseModel):
    """How well OUR product serves one job.

    Structurally a competitor audit's assessment with the other side removed. It carries
    no competitor score because there is no competitor here — a self-assessment is an
    audit whose subject is us, and reusing the two-sided shape with a dummy value would
    invite readers to compare against nothing.

    Assessed ONCE per job rather than re-derived inside each competitor audit, where the
    same job could otherwise carry a different "our" score in every report.
    """
    job_id: str = Field(description="Job ID from the product's job map (e.g., 'j1')")
    job_statement: str = Field(description="The full job statement")
    importance: str = Field(
        default="medium",
        description="How important this job is: critical, high, medium, or low"
    )
    score: int = Field(
        ge=0, le=10,
        description=(
            "How well our product serves this job (1-10, 0 if unknown), judged against "
            "the job itself — how completely it gets done for the customer"
        )
    )
    confidence: str = Field(
        default="medium",
        description=(
            "Confidence in this assessment: high, medium, or low. Use low when the only "
            "basis is the product's own description, with no independent evidence."
        )
    )
    score_rationale: str = Field(
        description="What drives the score — which capabilities carry the job and where it falls short"
    )
    features: List[JobFeatureAssessment] = Field(
        default=[],
        description="Our capabilities that serve this job (whose is always 'ours')"
    )
    outcome_coverage: List[OutcomeCoverage] = Field(
        default=[],
        description="How well each desired outcome is covered by our product"
    )
    evidence_ids: List[int] = Field(
        default=[],
        description="IDs of evidence records that informed this assessment"
    )


class SelfAssessmentOutput(BaseModel):
    """Complete output schema for SelfAssessmentAgent."""
    job_assessments: List[SelfJobAssessment] = Field(
        default=[],
        description="One assessment per job in the map"
    )
    evidence_based: bool = Field(
        default=False,
        description=(
            "Whether independent evidence informed this assessment. False means it rests "
            "only on the product's own description, which makes every score partly "
            "self-referential — the jobs were derived from that same description."
        )
    )
    assessment_summary: str = Field(
        default="",
        description="Two or three sentences on where the product is strong and weak across the map"
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
    unmapped_capabilities: List[UnmappedCapability] = Field(
        default=[],
        description="Competitor capabilities that fit no job in the map"
    )


# =============================================================================
# Staged Audit Schemas (Phase C)
#
# Splits the large single-call output into two calls:
# - Stage 1: competitor_context + functional_comparison + technical_constraints
#   (fast, ~45s for a small output)
# - Stage 2: job_assessments + evidence_citations + gaps_deep_dive
#   (slower, ~90-150s — uses Stage 1 output as conditioning context)
#
# The task merges both stage outputs back into FunctionalAuditOutput before
# persisting, so downstream consumers (report generator, synthesis) see the
# same shape they did pre-split.
# =============================================================================

class FunctionalAuditStage1Output(BaseModel):
    """Stage 1 of the staged audit: fast sections that can be returned early.

    Small enough to fit comfortably in max_tokens=8000 and complete in ~45s,
    giving the caller visible progress well before the heavier Stage 2.
    """
    competitor_context: CompetitorContext = Field(
        description="Section 0: Competitor context summary"
    )
    functional_comparison: List[FunctionalComparison] = Field(
        description="Section 1: Functional comparison table"
    )
    technical_constraints: TechnicalConstraints = Field(
        description="Section 3: Technical constraints and requirements"
    )


class FunctionalAuditStage2Output(BaseModel):
    """Stage 2 of the staged audit: heavy JTBD analysis.

    Conditioned on Stage 1 output (passed into the user prompt) so the agent
    doesn't re-derive context. Job assessments are the long tail; gaps_deep_dive
    is populated only when no job map is available.
    """
    job_assessments: List[JobAssessment] = Field(
        default=[],
        description="Per-job unified comparison (populated when job map is available)"
    )
    evidence_citations: List[EvidenceCitation] = Field(
        default=[],
        description="Evidence records cited in the analysis"
    )
    gaps_deep_dive: List[GapDeepDive] = Field(
        default=[],
        description="Deep-dive on gap features (populated when no job map)"
    )
    unmapped_capabilities: List[UnmappedCapability] = Field(
        default=[],
        description="Competitor capabilities that fit no job in the map"
    )


# =============================================================================
# API Response Schemas
# =============================================================================

class StoredFunctionalAuditOutput(FunctionalAuditOutput):
    """The audit as persisted, with our score joined in from the self-assessment.

    The agent's own output carries competitor scores only. This is the shape after
    enrichment, and it is what the markdown report is built from — otherwise the export
    would always claim our score was pending, even where a self-assessment exists.
    """
    job_assessments: List[StoredJobAssessment] = Field(
        default=[],
        description="Per-job comparison after our score and review state are joined in"
    )


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
    job_assessments: Optional[List[StoredJobAssessment]] = None
    evidence_citations: Optional[List[EvidenceCitation]] = None
    unmapped_capabilities: Optional[List[UnmappedCapability]] = None
    generated_at: Optional[str] = None
    queue_job_id: Optional[int] = None
