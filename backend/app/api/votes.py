"""
Voting API endpoints.

This file contains the endpoint for voting on ideas:
- POST /ideas/{idea_id}/vote - Vote on an idea (upvote or downvote)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.database import get_db
from app.models.idea import Idea
from app.models.vote import Vote
from app.models.user import User
from app.schemas.vote import VoteCreate, VoteResponse, VoteCountResponse, VoteActionResponse
from app.utils.security import get_current_active_user


# Create router (no prefix - will be included from main)
router = APIRouter(tags=["Votes"])


@router.post("/ideas/{idea_id}/vote", response_model=VoteActionResponse)
def vote_on_idea(
    idea_id: int,
    vote_data: VoteCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Vote on an idea.

    This is a protected endpoint - requires authentication.
    User can upvote (1) or downvote (-1).
    If user has already voted, their vote is updated.
    One vote per user per idea.

    Args:
        idea_id: ID of the idea to vote on
        vote_data: Vote value (1 or -1)
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated vote information and vote counts

    Raises:
        404 Not Found: If idea doesn't exist
    """
    # Check if idea exists
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea with id {idea_id} not found"
        )

    # Check if user has already voted on this idea
    existing_vote = db.query(Vote).filter(
        Vote.idea_id == idea_id,
        Vote.user_id == current_user.id
    ).first()

    if existing_vote:
        # Update existing vote
        old_value = existing_vote.vote_value
        existing_vote.vote_value = vote_data.vote_value
        db.commit()
        db.refresh(existing_vote)

        vote_record = existing_vote
        message = f"Vote updated from {old_value} to {vote_data.vote_value}"
    else:
        # Create new vote
        new_vote = Vote(
            idea_id=idea_id,
            user_id=current_user.id,
            vote_value=vote_data.vote_value
        )
        db.add(new_vote)
        db.commit()
        db.refresh(new_vote)

        vote_record = new_vote
        message = f"Vote cast: {vote_data.vote_value}"

    # Calculate updated vote counts
    result = db.query(
        func.sum(case((Vote.vote_value == 1, 1), else_=0)).label('upvotes'),
        func.sum(case((Vote.vote_value == -1, 1), else_=0)).label('downvotes'),
        func.sum(Vote.vote_value).label('score'),
        func.count(Vote.id).label('total_votes')
    ).filter(Vote.idea_id == idea_id).first()

    vote_counts = VoteCountResponse(
        idea_id=idea_id,
        upvotes=int(result.upvotes or 0),
        downvotes=int(result.downvotes or 0),
        score=int(result.score or 0),
        total_votes=int(result.total_votes or 0),
        user_vote=vote_data.vote_value
    )

    # Build vote response
    vote_response = VoteResponse(
        id=vote_record.id,
        idea_id=vote_record.idea_id,
        user_id=vote_record.user_id,
        vote_value=vote_record.vote_value,
        voted_at=vote_record.voted_at,
        updated_at=vote_record.updated_at
    )

    # Return complete action response
    return VoteActionResponse(
        vote=vote_response,
        vote_counts=vote_counts,
        message=message
    )
