"""
Pydantic schemas package.

Schemas define the shape of data coming in and out of the API.
"""

from app.schemas.auth import UserCreate, UserLogin, UserResponse, Token, UserRoleUpdate
from app.schemas.idea import IdeaCreate, IdeaResponse, IdeaListItem, IdeaListResponse, VoteCount
from app.schemas.vote import VoteCreate, VoteResponse, VoteCountResponse, VoteActionResponse
from app.schemas.submission import (
    SubmissionStructureRequest,
    SubmissionStructureResponse,
    SubmissionCreate,
    SubmissionResponse,
    SubmissionWithIdeaResponse
)

__all__ = [
    # Auth schemas
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "Token",
    "UserRoleUpdate",
    # Idea schemas
    "IdeaCreate",
    "IdeaResponse",
    "IdeaListItem",
    "IdeaListResponse",
    "VoteCount",
    # Vote schemas
    "VoteCreate",
    "VoteResponse",
    "VoteCountResponse",
    "VoteActionResponse",
    # Submission schemas
    "SubmissionStructureRequest",
    "SubmissionStructureResponse",
    "SubmissionCreate",
    "SubmissionResponse",
    "SubmissionWithIdeaResponse",
]
