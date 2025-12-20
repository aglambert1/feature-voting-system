"""
Pydantic schemas for competitor intelligence requests and responses.

These schemas validate incoming data and serialize outgoing data for the CI API.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ============================================================================
# Product Schemas
# ============================================================================

class ProductBase(BaseModel):
    """Base schema for product data."""
    product_name: str = Field(..., min_length=1, max_length=255)
    product_description: str = Field(..., min_length=10)


class ProductCreate(ProductBase):
    """Schema for creating a new CI product."""
    product_source_type: str = Field(..., pattern="^(text|document|url)$")
    product_source_data: Optional[Dict[str, Any]] = None


class ProductUpdate(BaseModel):
    """Schema for updating a product."""
    product_name: Optional[str] = Field(None, min_length=1, max_length=255)
    product_description: Optional[str] = Field(None, min_length=10)
    status: Optional[str] = None


class ProductResponse(ProductBase):
    """Schema for returning product information."""
    id: int
    user_id: int
    product_category: Optional[str]
    structured_product_data: Optional[Dict[str, Any]]
    last_analyzed_at: Optional[datetime]
    analysis_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    """Schema for returning list of products."""
    products: List[ProductResponse]
    total: int


# ============================================================================
# Session Schemas
# ============================================================================

class AnalyzedProduct(BaseModel):
    """Structured product analysis from AI."""
    product_name: str
    product_category: str
    core_features: List[str]
    target_users: str
    value_propositions: List[str]
    competitor_search_keywords: List[str]


class SessionCreate(BaseModel):
    """Schema for creating a new analysis session."""
    product_id: Optional[int] = None  # If selecting existing product
    product_name: Optional[str] = Field(None, min_length=1, max_length=255)  # If creating new
    product_description: Optional[str] = Field(None, min_length=10)  # Required if creating new
    session_name: Optional[str] = None
    product_source_type: str = Field(..., pattern="^(text|document|url)$")
    product_source_data: Optional[Dict[str, Any]] = None
    enable_comparison: bool = Field(default=True, description="Enable differential analysis if previous sessions exist")
    previous_session_id: Optional[int] = Field(None, description="Deprecated: use compare_to_session_id instead")
    compare_to_session_id: Optional[int] = Field(None, description="Explicit session ID to compare against for differential analysis")


class SessionResponse(BaseModel):
    """Schema for returning session information."""
    id: int
    product_id: int
    user_id: int
    session_number: int
    session_name: Optional[str]
    analysis_type: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class SessionDetailResponse(SessionResponse):
    """Detailed session response with relationships."""
    analyzed_product_structure: Optional[Dict[str, Any]]
    comparison_to_session_id: Optional[int]
    updated_at: datetime


# ============================================================================
# Competitor Schemas
# ============================================================================

class CompetitorBase(BaseModel):
    """Base schema for competitor data."""
    competitor_name: str = Field(..., min_length=1, max_length=255)
    competitor_url: Optional[str] = Field(None, max_length=500)


class SessionCompetitorCreate(CompetitorBase):
    """Schema for creating a session competitor."""
    ai_summary: Optional[str] = None
    discovery_source: str
    discovery_rank: Optional[int] = None


class SessionCompetitorResponse(BaseModel):
    """Schema for returning session competitor."""
    id: int
    session_id: int
    product_competitor_id: Optional[int]
    competitor_name: str
    competitor_url: Optional[str]
    ai_summary: Optional[str]
    discovery_source: str
    is_new_discovery: bool
    selected_by_user: bool
    discovery_rank: Optional[int]
    status_change: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CompetitorUpdateSelection(BaseModel):
    """Schema for updating competitor selection."""
    competitor_ids: List[int] = Field(..., description="List of session competitor IDs to select")


# ============================================================================
# Feature Schemas
# ============================================================================

class FeatureBase(BaseModel):
    """Base schema for feature data."""
    feature_name: str = Field(..., min_length=1, max_length=255)
    feature_description: Optional[str] = None
    feature_category: Optional[str] = Field(None, max_length=100)


class CompetitorFeatureCreate(FeatureBase):
    """Schema for creating a competitor feature."""
    session_competitor_id: int
    extraction_confidence: Optional[float] = Field(None, ge=0, le=1)
    source_url: Optional[str] = Field(None, max_length=500)
    raw_context: Optional[str] = None


class CompetitorFeatureResponse(BaseModel):
    """Schema for returning competitor feature."""
    id: int
    session_competitor_id: int
    product_feature_id: Optional[int]
    feature_name: str
    feature_description: Optional[str]
    feature_category: Optional[str]
    extraction_confidence: Optional[float]
    source_url: Optional[str]
    change_type: Optional[str]
    change_description: Optional[str]
    selected_by_user: bool
    detail_requested: bool
    expanded_description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class FeatureUpdateSelection(BaseModel):
    """Schema for updating feature selection."""
    feature_ids: List[int] = Field(..., description="List of feature IDs to select")


class FeatureRequestDetail(BaseModel):
    """Schema for requesting detailed feature information."""
    feature_id: int


# ============================================================================
# Generated Idea Schemas
# ============================================================================

class GeneratedIdeaBase(BaseModel):
    """Base schema for generated idea data."""
    idea_what: str = Field(..., min_length=10)
    idea_why: str = Field(..., min_length=10)
    idea_use_case: str = Field(..., min_length=10)


class GeneratedIdeaCreate(GeneratedIdeaBase):
    """Schema for creating a generated idea."""
    feature_id: int
    session_id: int
    product_id: int
    is_differential: bool = False


class GeneratedIdeaUpdate(BaseModel):
    """Schema for updating a generated idea."""
    idea_what: Optional[str] = Field(None, min_length=10)
    idea_why: Optional[str] = Field(None, min_length=10)
    idea_use_case: Optional[str] = Field(None, min_length=10)


class GeneratedIdeaResponse(GeneratedIdeaBase):
    """Schema for returning generated idea."""
    id: int
    feature_id: int
    session_id: int
    product_id: int
    is_differential: bool
    user_edited: bool
    user_approved: bool
    submitted_to_ideas: bool
    final_idea_id: Optional[int]
    created_at: datetime
    edited_at: Optional[datetime]

    class Config:
        from_attributes = True


class IdeaApprovalUpdate(BaseModel):
    """Schema for approving ideas for submission."""
    idea_ids: List[int] = Field(..., description="List of generated idea IDs to approve")


class IdeaSubmitToVoting(BaseModel):
    """Schema for submitting ideas to the main voting system."""
    idea_ids: List[int] = Field(..., description="List of generated idea IDs to submit")


# ============================================================================
# Agent Log Schemas
# ============================================================================

class AgentLogCreate(BaseModel):
    """Schema for creating an agent execution log."""
    session_id: Optional[int] = None
    product_id: Optional[int] = None
    agent_name: str = Field(..., max_length=100)
    stage: str = Field(..., max_length=50)
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    llm_tokens_used: Optional[int] = None
    execution_time_ms: Optional[int] = None
    status: str = Field(..., pattern="^(success|failure|pending)$")
    error_message: Optional[str] = None


class AgentLogResponse(BaseModel):
    """Schema for returning agent execution log."""
    id: int
    session_id: Optional[int]
    product_id: Optional[int]
    agent_name: str
    stage: str
    status: str
    llm_tokens_used: Optional[int]
    execution_time_ms: Optional[int]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Dashboard/Summary Schemas
# ============================================================================

class SessionSummary(BaseModel):
    """Summary of a session's progress."""
    session: SessionResponse
    competitors_count: int
    features_count: int
    ideas_count: int
    new_competitors: int
    new_features: int


class ProductDashboard(BaseModel):
    """Dashboard view of a product's CI data."""
    product: ProductResponse
    total_sessions: int
    total_competitors: int
    total_features: int
    total_ideas: int
    pending_ideas: int
    recent_sessions: List[SessionResponse]
