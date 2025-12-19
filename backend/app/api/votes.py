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
    Vote on an idea (upvote only).

    This is a protected endpoint - requires authentication.
    User can only upvote (1). Downvoting has been removed.
    If user clicks upvote again, it removes their vote (unvote).
    One vote per user per idea.

    Args:
        idea_id: ID of the idea to vote on
        vote_data: Vote value (must be 1 for upvote)
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated vote information and vote counts

    Raises:
        404 Not Found: If idea doesn't exist
        400 Bad Request: If vote value is not 1
    """
    # Only allow upvotes (value = 1)
    if vote_data.vote_value != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only upvotes (value=1) are allowed. Use DELETE endpoint to remove vote."
        )

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
        # User already voted - this is an "unvote" action (remove vote)
        db.delete(existing_vote)
        db.commit()

        message = "Vote removed"
        user_vote_value = None
        vote_record = None
    else:
        # Create new upvote
        new_vote = Vote(
            idea_id=idea_id,
            user_id=current_user.id,
            vote_value=1
        )
        db.add(new_vote)
        db.commit()
        db.refresh(new_vote)

        vote_record = new_vote
        message = "Upvote cast"
        user_vote_value = 1

    # Calculate updated vote counts
    result = db.query(
        func.count(Vote.id).label('total_votes'),
        func.sum(Vote.vote_value).label('score')
    ).filter(Vote.idea_id == idea_id).first()

    # Score is now just the count of upvotes (no downvotes)
    total_votes = int(result.total_votes or 0)
    score = int(result.score or 0)  # This equals total_votes since all votes are +1

    vote_counts = VoteCountResponse(
        idea_id=idea_id,
        upvotes=total_votes,
        downvotes=0,  # No downvotes anymore
        score=score,
        total_votes=total_votes,
        user_vote=user_vote_value
    )

    # Build vote response (None if unvoted)
    vote_response = None
    if vote_record:
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
