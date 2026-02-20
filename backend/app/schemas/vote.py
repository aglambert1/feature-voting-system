"""
Pydantic schemas for vote-related requests and responses.

These schemas validate voting actions and return vote information.
"""

from datetime import datetime
from pydantic import BaseModel, Field, validator


class VoteCreate(BaseModel):
    """
    Schema for creating a vote.

    User can upvote (1) or remove their vote by voting again.
    """
    vote_value: int = Field(..., description="Vote value: must be 1 (upvote)")

    @validator('vote_value')
    def validate_vote_value(cls, v):
        """Ensure vote value is 1 (upvote only)."""
        if v != 1:
            raise ValueError('Vote value must be 1 (upvote)')
        return v


class VoteResponse(BaseModel):
    """
    Schema for returning vote information.

    Sent back after a successful vote.
    """
    id: int
    idea_id: int
    user_id: int
    vote_value: int
    voted_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VoteCountResponse(BaseModel):
    """
    Schema for returning vote statistics for an idea.

    Used to show updated vote counts after voting.
    """
    idea_id: int
    upvotes: int = Field(description="Number of upvotes")
    total_votes: int = Field(description="Total number of votes")
    user_vote: int | None = Field(description="Current user's vote (1 or null)")


class VoteActionResponse(BaseModel):
    """
    Schema for complete vote action response.

    Returns both the vote record and updated vote counts.
    Vote can be None if the user removed their vote (unvote).
    """
    vote: VoteResponse | None
    vote_counts: VoteCountResponse
    message: str = Field(description="Success message")
