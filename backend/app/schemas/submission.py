"""
Pydantic schemas for submission-related requests and responses.

These handle the AI-powered idea submission flow.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class SubmissionStructureRequest(BaseModel):
    """
    Schema for requesting AI structuring of freeform text.

    User submits their idea in natural language,
    and AI structures it into what/why/use_case format.
    """
    freeform_text: str = Field(
        ...,
        min_length=20,
        max_length=5000,
        description="User's freeform idea description"
    )
    product_id: int = Field(..., description="Product ID for context-aware structuring")


class SubmissionStructureResponse(BaseModel):
    """
    Schema for AI-structured idea output.

    This is what the AI returns after processing freeform text.
    """
    title: str = Field(description="AI-generated title")
    what_description: str = Field(description="What is the feature?")
    why_description: str = Field(description="Why is it valuable?")
    use_case_description: str = Field(description="How would it be used?")
    processing_time: float = Field(description="Time taken to structure (seconds)")


class SubmissionCreate(BaseModel):
    """
    Schema for submitting a complete idea with tracking.

    Includes both the original freeform text and the structured version
    (which may have been edited by the user).
    """
    # Original input
    original_freeform_text: str = Field(..., min_length=20, description="Original text user typed")

    # Structured idea (possibly edited by user)
    title: str = Field(..., min_length=3, max_length=255)
    what_description: str = Field(..., min_length=10)
    why_description: str = Field(..., min_length=10)
    use_case_description: str = Field(..., min_length=10)
    category: Optional[str] = Field(None, max_length=100)
    product_id: int = Field(..., description="Product ID (required)")

    # AI-generated version (before user edits)
    ai_structured_version: Optional[dict] = Field(
        None,
        description="Original AI output (for tracking edits)"
    )

    # Metadata
    structuring_time_seconds: Optional[int] = Field(
        None,
        description="Time AI took to structure text"
    )


class SubmissionResponse(BaseModel):
    """
    Schema for returning submission information.

    Sent back after successful idea submission.
    """
    id: int
    idea_id: int
    submitter_id: int
    original_freeform_text: str
    ai_structured_version: Optional[dict]
    user_edits: Optional[dict]
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmissionWithIdeaResponse(BaseModel):
    """
    Schema for complete submission response including created idea.

    Returns both the submission record and the created idea.
    """
    submission: SubmissionResponse
    idea_id: int
    idea_title: str
    message: str = Field(description="Success message")
