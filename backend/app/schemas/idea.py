"""
Pydantic schemas for idea-related requests and responses.

These schemas validate incoming data and serialize outgoing data.
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional

from app.models.idea import SourceType, IdeaStatus


class IdeaCreate(BaseModel):
    """
    Schema for creating a new idea.

    Used when submitting a new idea (manual submission).
    """
    title: str = Field(..., min_length=3, max_length=255, description="Idea title")
    what_description: str = Field(..., min_length=10, description="What is the feature?")
    why_description: str = Field(..., min_length=10, description="Why is it valuable?")
    use_case_description: str = Field(..., min_length=10, description="How would it be used?")
    category: Optional[str] = Field(None, max_length=100, description="Optional category")
    product_id: int = Field(..., description="Product ID (required)")


class VoteCount(BaseModel):
    """
    Schema for vote statistics.

    Contains aggregated vote counts for an idea.
    """
    upvotes: int = Field(default=0, description="Number of upvotes")
    downvotes: int = Field(default=0, description="Number of downvotes")
    score: int = Field(default=0, description="Net score (upvotes - downvotes)")
    total_votes: int = Field(default=0, description="Total number of votes")


class IdeaResponse(BaseModel):
    """
    Schema for returning a single idea with vote counts.

    This is what the API sends back when you request idea info.
    """
    id: int
    title: str
    what_description: str
    why_description: str
    use_case_description: str
    category: Optional[str]
    source_type: SourceType
    status: IdeaStatus
    created_at: datetime
    updated_at: datetime
    product_id: int
    product_name: Optional[str] = None

    # Vote counts (aggregated)
    vote_counts: VoteCount

    # User's vote on this idea (if authenticated)
    user_vote: Optional[int] = Field(None, description="Current user's vote: 1, -1, or null")

    class Config:
        from_attributes = True


class IdeaListItem(BaseModel):
    """
    Schema for idea in a list view (less detail than full response).

    Optimized for displaying multiple ideas efficiently.
    """
    id: int
    title: str
    what_description: str
    why_description: Optional[str] = None
    use_case_description: Optional[str] = None
    category: Optional[str]
    created_at: datetime
    product_id: int
    product_name: Optional[str] = None

    # Triage status for display
    triage_status: Optional[str] = None
    is_active: Optional[bool] = None
    auto_responded: Optional[bool] = None
    duplicate_of_idea_id: Optional[int] = None
    duplicate_of_title: Optional[str] = None

    # Vote counts
    vote_counts: VoteCount

    # User's vote
    user_vote: Optional[int] = None
    user_vote_timestamp: Optional[datetime] = None  # When user voted (if they did)

    class Config:
        from_attributes = True


class IdeaListResponse(BaseModel):
    """
    Schema for returning a list of ideas.

    Includes pagination info (for future use).
    """
    ideas: list[IdeaListItem]
    total: int = Field(description="Total number of ideas")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=100, description="Number of items per page")


class SimilarIdeaResponse(BaseModel):
    """
    Schema for similar ideas search results.

    Returns minimal information about similar ideas with similarity score.
    Used for duplicate detection during idea submission.
    """
    id: int = Field(description="Idea ID")
    title: str = Field(description="Idea title")
    what_description: str = Field(description="What is the feature?")
    similarity_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Similarity score (0.0 to 1.0, where 1.0 is identical)"
    )

    class Config:
        from_attributes = True
