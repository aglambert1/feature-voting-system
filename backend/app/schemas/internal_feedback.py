"""
Pydantic schemas for internal feedback import and theme extraction.

These schemas define:
- Input format for JSON file imports (deals and support tickets)
- Output schemas for the Internal Discovery Agent (themes)
- API request/response models
"""

from typing import List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Input Schemas (File Import Format)
# =============================================================================

class DealInput(BaseModel):
    """A single deal record from CRM export."""
    id: str = Field(description="Unique identifier for the deal")
    outcome: Literal["won", "lost"] = Field(
        description="Deal outcome: won or lost"
    )
    competitor_name: Optional[str] = Field(
        default=None,
        description="Name of competitor involved (if any)"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Win/loss reason provided by sales rep"
    )
    deal_value: Optional[float] = Field(
        default=None,
        description="Deal value in dollars"
    )
    close_date: Optional[str] = Field(
        default=None,
        description="Date deal was closed (ISO format)"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional notes from sales rep"
    )


class SupportTicketInput(BaseModel):
    """A single support ticket or aggregated theme from support system."""
    id: str = Field(description="Unique identifier for the ticket/theme")
    category: Literal["feature_request", "bug", "support", "other"] = Field(
        default="other",
        description="Category of the ticket"
    )
    subject: str = Field(description="Ticket subject or theme name")
    description: Optional[str] = Field(
        default=None,
        description="Ticket description or details"
    )
    tags: List[str] = Field(
        default=[],
        description="Tags associated with the ticket"
    )
    ticket_count: int = Field(
        default=1,
        description="Number of tickets with this theme (for aggregated data)"
    )
    created_at: Optional[str] = Field(
        default=None,
        description="Creation date (ISO format)"
    )


class InternalFeedbackFileInput(BaseModel):
    """
    Schema for the JSON file uploaded by users.

    This format is designed to mirror CRM/support system exports
    and support future live integrations.
    """
    source: str = Field(
        default="file_import",
        description="Data source: file_import, hubspot, salesforce, zendesk, etc."
    )
    imported_at: Optional[str] = Field(
        default=None,
        description="Timestamp when data was exported (ISO format)"
    )
    deals: List[DealInput] = Field(
        default=[],
        description="List of deal records"
    )
    support_tickets: List[SupportTicketInput] = Field(
        default=[],
        description="List of support tickets or themes"
    )


# =============================================================================
# Output Schemas (Internal Discovery Agent Output)
# =============================================================================

class WinLossThemeOutput(BaseModel):
    """A synthesized theme from win/loss deal data."""
    theme_name: str = Field(
        description="Name of the identified theme (e.g., 'Missing Time Tracking')"
    )
    outcome: Literal["won", "lost", "both"] = Field(
        description="Whether this theme relates to wins, losses, or both"
    )
    competitor_correlation: Optional[str] = Field(
        default=None,
        description="Competitor most associated with this theme (if any)"
    )
    deal_count: int = Field(
        description="Number of deals mentioning this theme"
    )
    total_value: float = Field(
        default=0.0,
        description="Total deal value associated with this theme"
    )
    sample_reasons: List[str] = Field(
        default=[],
        description="Sample quotes/reasons from deals (up to 5)"
    )
    feature_keywords: List[str] = Field(
        default=[],
        description="Keywords that could match competitive features"
    )
    jtbd_statement: Optional[str] = Field(
        default=None,
        description="The customer job this theme relates to: 'When [situation], I want to [motivation], so I can [outcome]'"
    )


class SupportThemeOutput(BaseModel):
    """A synthesized theme from support ticket data."""
    theme_name: str = Field(
        description="Name of the identified theme"
    )
    category: str = Field(
        description="Primary category (feature_request, bug, etc.)"
    )
    ticket_count: int = Field(
        description="Total tickets related to this theme"
    )
    sample_subjects: List[str] = Field(
        default=[],
        description="Sample ticket subjects (up to 5)"
    )
    feature_keywords: List[str] = Field(
        default=[],
        description="Keywords that could match competitive features"
    )
    urgency_indicator: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="Assessed urgency based on ticket volume and recency"
    )
    jtbd_statement: Optional[str] = Field(
        default=None,
        description="The customer job this theme relates to: 'When [situation], I want to [motivation], so I can [outcome]'"
    )


class InternalDiscoveryOutput(BaseModel):
    """
    Complete output schema for Internal Discovery Agent.

    Produced by analyzing imported deals and support tickets
    to extract themes for synthesis.
    """
    winloss_themes: List[WinLossThemeOutput] = Field(
        default=[],
        description="Themes extracted from win/loss data"
    )
    support_themes: List[SupportThemeOutput] = Field(
        default=[],
        description="Themes extracted from support ticket data"
    )
    analysis_summary: str = Field(
        description="Brief summary of key findings"
    )
    deals_analyzed: int = Field(
        description="Total number of deals processed"
    )
    tickets_analyzed: int = Field(
        description="Total number of tickets processed"
    )


# =============================================================================
# API Request/Response Schemas
# =============================================================================

class InternalFeedbackImportCreate(BaseModel):
    """Request schema for creating a new import."""
    filename: str = Field(description="Original filename")
    source_type: str = Field(
        default="file_import",
        description="Source type (file_import, etc.)"
    )


class InternalFeedbackImportResponse(BaseModel):
    """Response schema for import records."""
    id: int
    product_id: int
    filename: str
    source_type: str
    status: str
    imported_at: datetime
    deals_count: int
    tickets_count: int
    themes_extracted: bool
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class WinLossThemeResponse(BaseModel):
    """Response schema for win/loss themes."""
    id: int
    import_id: int
    theme_name: str
    outcome: str
    competitor_name: Optional[str]
    deal_count: int
    total_value: float
    sample_reasons: List[str]
    feature_keywords: List[str]

    model_config = ConfigDict(from_attributes=True)


class SupportThemeResponse(BaseModel):
    """Response schema for support themes."""
    id: int
    import_id: int
    theme_name: str
    category: str
    ticket_count: int
    sample_subjects: List[str]
    feature_keywords: List[str]
    urgency_indicator: str

    model_config = ConfigDict(from_attributes=True)


class ThemesResponse(BaseModel):
    """Response schema for all themes from an import."""
    import_id: int
    winloss_themes: List[WinLossThemeResponse]
    support_themes: List[SupportThemeResponse]
    analysis_summary: Optional[str]
