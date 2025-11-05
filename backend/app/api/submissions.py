"""
Submissions API endpoints.

This file contains endpoints for the AI-powered idea submission flow:
- POST /submissions/structure - Structure freeform text with AI
- POST /submissions/submit - Submit a complete idea with tracking
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import time

from app.database import get_db
from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.submission import Submission
from app.models.user import User
from app.schemas.submission import (
    SubmissionStructureRequest,
    SubmissionStructureResponse,
    SubmissionCreate,
    SubmissionWithIdeaResponse,
    SubmissionResponse
)
from app.services.llm_service import llm_service
from app.utils.security import get_current_active_user


# Create router with /submissions prefix
router = APIRouter(prefix="/submissions", tags=["Submissions"])


@router.post("/structure", response_model=SubmissionStructureResponse)
async def structure_freeform_text(
    request: SubmissionStructureRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Structure freeform text into a structured idea format using AI.

    This endpoint takes natural language input and uses Claude API
    to structure it into what/why/use_case format.

    This is a protected endpoint - requires authentication.

    Args:
        request: Freeform text from user
        current_user: Authenticated user

    Returns:
        Structured idea with title, what, why, use_case

    Raises:
        500 Internal Server Error: If AI processing fails
    """
    try:
        # Call LLM service to structure the text
        structured_data = llm_service.structure_idea(request.freeform_text)

        # Return structured response
        return SubmissionStructureResponse(
            title=structured_data["title"],
            what_description=structured_data["what_description"],
            why_description=structured_data["why_description"],
            use_case_description=structured_data["use_case_description"],
            processing_time=structured_data["processing_time"]
        )

    except Exception as e:
        # Log the error and return 500
        print(f"Error structuring text: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to structure text: {str(e)}"
        )


@router.post("/submit", response_model=SubmissionWithIdeaResponse, status_code=status.HTTP_201_CREATED)
async def submit_idea(
    submission_data: SubmissionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Submit a complete idea with tracking.

    This endpoint creates both an Idea record and a Submission record
    to track the original freeform text and AI processing details.

    This is a protected endpoint - requires authentication.

    Args:
        submission_data: Complete submission with original text and structured data
        current_user: Authenticated user
        db: Database session

    Returns:
        Created idea and submission information

    Raises:
        400 Bad Request: If data validation fails
    """
    # Create the idea first
    new_idea = Idea(
        title=submission_data.title,
        what_description=submission_data.what_description,
        why_description=submission_data.why_description,
        use_case_description=submission_data.use_case_description,
        category=submission_data.category,
        source_type=SourceType.MANUAL,
        submitter_id=current_user.id,
        status=IdeaStatus.ACTIVE
    )

    db.add(new_idea)
    db.flush()  # Get the idea ID without committing

    # Calculate user edits (compare AI version to final version)
    user_edits = None
    if submission_data.ai_structured_version:
        user_edits = {
            "title_edited": submission_data.title != submission_data.ai_structured_version.get("title"),
            "what_edited": submission_data.what_description != submission_data.ai_structured_version.get("what"),
            "why_edited": submission_data.why_description != submission_data.ai_structured_version.get("why"),
            "use_case_edited": submission_data.use_case_description != submission_data.ai_structured_version.get("use_case")
        }

    # Create submission record for tracking
    new_submission = Submission(
        idea_id=new_idea.id,
        submitter_id=current_user.id,
        original_freeform_text=submission_data.original_freeform_text,
        ai_structured_version=submission_data.ai_structured_version,
        user_edits=user_edits,
        structuring_time_seconds=submission_data.structuring_time_seconds
    )

    db.add(new_submission)
    db.commit()
    db.refresh(new_idea)
    db.refresh(new_submission)

    # Build response
    submission_response = SubmissionResponse(
        id=new_submission.id,
        idea_id=new_submission.idea_id,
        submitter_id=new_submission.submitter_id,
        original_freeform_text=new_submission.original_freeform_text,
        ai_structured_version=new_submission.ai_structured_version,
        user_edits=new_submission.user_edits,
        submitted_at=new_submission.submitted_at
    )

    return SubmissionWithIdeaResponse(
        submission=submission_response,
        idea_id=new_idea.id,
        idea_title=new_idea.title,
        message=f"Idea '{new_idea.title}' submitted successfully"
    )
