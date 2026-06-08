"""
Pydantic schemas for JTBD Job Map.

Defines input/output schemas for:
- Target customer profile
- Job map (hierarchical JTBD structure)
- Individual job CRUD operations
- JobMapExtractorAgent output
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class TargetCustomerProfile(BaseModel):
    """Structured target customer persona."""
    persona_name: str = Field(description="Name for this persona, e.g. 'Mid-market Operations Director'")
    company_characteristics: Optional[str] = Field(default=None, description="Company size, industry, stage")
    key_traits: List[str] = Field(default=[], description="Key behavioral traits or constraints")
    hiring_criteria: Optional[str] = Field(default=None, description="What would make them 'hire' this product?")


class DesiredOutcome(BaseModel):
    """A measurable outcome the customer wants from a job."""
    statement: str = Field(description="Outcome statement, ideally measurable")
    direction: Literal["minimize", "maximize", "achieve"] = Field(
        default="achieve",
        description="Whether customer wants to minimize, maximize, or achieve this outcome"
    )


class JobStatement(BaseModel):
    """A single job in the JTBD hierarchy."""
    job_id: str = Field(description="Unique key within the job map, e.g. 'j1', 'je1', 'js1'")
    job_type: Literal["functional", "emotional", "social"] = Field(
        description="Dimension of the job"
    )
    statement: str = Field(
        description="Job statement: 'When [situation], I want to [action/feeling], so I can [outcome]'"
    )
    desired_outcomes: List[str] = Field(
        default=[],
        description="Measurable desired outcomes for this job"
    )
    importance: Literal["critical", "high", "medium", "low"] = Field(
        default="medium",
        description="How important this job is to the target customer"
    )


class JobMap(BaseModel):
    """Hierarchical JTBD job map for a product."""
    main_job: str = Field(
        description="The overall progress the customer is trying to make"
    )
    functional_jobs: List[JobStatement] = Field(
        default=[],
        description="Functional sub-jobs (the practical things customers need to accomplish)"
    )
    emotional_jobs: List[JobStatement] = Field(
        default=[],
        description="Emotional sub-jobs (how customers want to feel)"
    )
    social_jobs: List[JobStatement] = Field(
        default=[],
        description="Social sub-jobs (how customers want to be perceived)"
    )


class JobMapExtractionOutput(BaseModel):
    """Output schema for JobMapExtractorAgent."""
    target_customer_profile: TargetCustomerProfile = Field(
        description="Inferred target customer persona"
    )
    job_map: JobMap = Field(
        description="Proposed hierarchical JTBD job map"
    )
    extraction_notes: Optional[str] = Field(
        default=None,
        description="Notes about assumptions or areas needing PO input"
    )


# --- API Request/Response Schemas ---

class JobCreateRequest(BaseModel):
    """Request to add a single job to the map."""
    job_id: str = Field(description="Unique key, e.g. 'j4'")
    job_type: Literal["functional", "emotional", "social"] = "functional"
    statement: str
    desired_outcomes: List[str] = Field(default=[])
    importance: Literal["critical", "high", "medium", "low"] = "medium"


class JobUpdateRequest(BaseModel):
    """Request to update a job (partial update)."""
    statement: Optional[str] = None
    desired_outcomes: Optional[List[str]] = None
    importance: Optional[Literal["critical", "high", "medium", "low"]] = None


class JobResponse(BaseModel):
    """Response for a single job."""
    id: int
    job_id_key: str
    job_type: str
    statement: str
    desired_outcomes: Optional[list] = None
    importance: str
    has_embedding: bool = False
    signal_count: int = 0
    updated_at: Optional[str] = None


class JobMapResponse(BaseModel):
    """Full job map response including target customer."""
    product_id: int
    product_name: str
    target_customer_profile: Optional[TargetCustomerProfile] = None
    job_map: Optional[JobMap] = None
    job_map_version: int = 0
    job_map_last_updated: Optional[str] = None
    jobs: List[JobResponse] = Field(default=[], description="Individual job records from DB")
