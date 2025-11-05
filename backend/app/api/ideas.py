"""
Ideas API endpoints.

This file contains all endpoints for managing ideas:
- POST /ideas - Create a new idea
- GET /ideas - List all ideas with vote counts
- GET /ideas/{id} - Get a single idea
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import Optional

from app.database import get_db
from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.vote import Vote
from app.models.user import User
from app.schemas.idea import IdeaCreate, IdeaResponse, IdeaListItem, IdeaListResponse, VoteCount
from app.utils.security import get_current_active_user, get_current_user


# Create router with /ideas prefix
router = APIRouter(prefix="/ideas", tags=["Ideas"])


def get_vote_counts(db: Session, idea_id: int) -> VoteCount:
    """
    Calculate vote counts for a specific idea.

    Args:
        db: Database session
        idea_id: ID of the idea

    Returns:
        VoteCount object with aggregated statistics
    """
    result = db.query(
        func.sum(case((Vote.vote_value == 1, 1), else_=0)).label('upvotes'),
        func.sum(case((Vote.vote_value == -1, 1), else_=0)).label('downvotes'),
        func.sum(Vote.vote_value).label('score'),
        func.count(Vote.id).label('total_votes')
    ).filter(Vote.idea_id == idea_id).first()

    return VoteCount(
        upvotes=int(result.upvotes or 0),
        downvotes=int(result.downvotes or 0),
        score=int(result.score or 0),
        total_votes=int(result.total_votes or 0)
    )


def get_user_vote(db: Session, idea_id: int, user_id: Optional[int]) -> Optional[int]:
    """
    Get the current user's vote on an idea.

    Args:
        db: Database session
        idea_id: ID of the idea
        user_id: ID of the user (None if not authenticated)

    Returns:
        Vote value (1, -1, or None)
    """
    if user_id is None:
        return None

    vote = db.query(Vote).filter(
        Vote.idea_id == idea_id,
        Vote.user_id == user_id
    ).first()

    return vote.vote_value if vote else None


@router.post("/", response_model=IdeaResponse, status_code=status.HTTP_201_CREATED)
def create_idea(
    idea_data: IdeaCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new idea.

    This is a protected endpoint - requires authentication.
    Creates an idea and links it to the current user.

    Args:
        idea_data: Idea creation data (title, what, why, use_case)
        current_user: Authenticated user
        db: Database session

    Returns:
        The created idea with ID and vote counts
    """
    # Create new idea
    new_idea = Idea(
        title=idea_data.title,
        what_description=idea_data.what_description,
        why_description=idea_data.why_description,
        use_case_description=idea_data.use_case_description,
        category=idea_data.category,
        source_type=SourceType.MANUAL,
        submitter_id=current_user.id,
        status=IdeaStatus.ACTIVE
    )

    db.add(new_idea)
    db.commit()
    db.refresh(new_idea)

    # Get vote counts (will be 0 for new idea)
    vote_counts = get_vote_counts(db, new_idea.id)

    # Build response
    response = IdeaResponse(
        id=new_idea.id,
        title=new_idea.title,
        what_description=new_idea.what_description,
        why_description=new_idea.why_description,
        use_case_description=new_idea.use_case_description,
        category=new_idea.category,
        source_type=new_idea.source_type,
        status=new_idea.status,
        created_at=new_idea.created_at,
        updated_at=new_idea.updated_at,
        vote_counts=vote_counts,
        user_vote=None  # New idea, user hasn't voted yet
    )

    return response


@router.get("/", response_model=IdeaListResponse)
def list_ideas(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all active ideas with vote counts.

    This is a public endpoint (no authentication required).
    Ideas are sorted by score (highest first).

    Args:
        skip: Number of items to skip (pagination)
        limit: Maximum number of items to return
        db: Database session

    Returns:
        List of ideas with vote counts
    """
    # Get all active ideas
    ideas = db.query(Idea).filter(
        Idea.status == IdeaStatus.ACTIVE
    ).all()

    # Build list items with vote counts
    idea_items = []
    for idea in ideas:
        vote_counts = get_vote_counts(db, idea.id)
        user_vote = None  # TODO: Add optional auth to show user's votes

        idea_items.append(IdeaListItem(
            id=idea.id,
            title=idea.title,
            what_description=idea.what_description,
            why_description=idea.why_description,
            use_case_description=idea.use_case_description,
            category=idea.category,
            created_at=idea.created_at,
            vote_counts=vote_counts,
            user_vote=user_vote
        ))

    # Sort by score (highest first)
    idea_items.sort(key=lambda x: x.vote_counts.score, reverse=True)

    # Apply pagination
    paginated_items = idea_items[skip:skip + limit]

    return IdeaListResponse(
        ideas=paginated_items,
        total=len(ideas),
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit
    )


@router.get("/{idea_id}", response_model=IdeaResponse)
def get_idea(
    idea_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single idea by ID.

    This is a public endpoint (no authentication required).
    Returns full idea details with vote counts.

    Args:
        idea_id: ID of the idea to retrieve
        db: Database session

    Returns:
        Full idea details with vote counts

    Raises:
        404 Not Found: If idea doesn't exist
    """
    # Find the idea
    idea = db.query(Idea).filter(Idea.id == idea_id).first()

    if not idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea with id {idea_id} not found"
        )

    # Get vote counts
    vote_counts = get_vote_counts(db, idea.id)
    user_vote = None  # TODO: Add optional auth to show user's vote

    # Build response
    response = IdeaResponse(
        id=idea.id,
        title=idea.title,
        what_description=idea.what_description,
        why_description=idea.why_description,
        use_case_description=idea.use_case_description,
        category=idea.category,
        source_type=idea.source_type,
        status=idea.status,
        created_at=idea.created_at,
        updated_at=idea.updated_at,
        vote_counts=vote_counts,
        user_vote=user_vote
    )

    return response
