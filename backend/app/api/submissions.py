"""
Submissions API endpoints.

This file contains endpoints for the AI-powered idea submission flow:
- POST /submissions/structure - Structure freeform text with AI
- POST /submissions/submit - Submit a complete idea with tracking
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import time

from app.database import get_db
from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.idea_status_history import IdeaStatusHistory
from app.models.submission import Submission
from app.models.user import User
from app.models.competitor_intelligence import CIProduct, ProductPermissionLevel
from app.models.queue import JobType
from app.schemas.submission import (
    SubmissionStructureRequest,
    SubmissionStructureResponse,
    SubmissionCreate,
    SubmissionWithIdeaResponse,
    SubmissionResponse
)
from app.services.llm_service import llm_service
from app.services.permission_service import PermissionService
from app.services.vector_service import VectorService
from app.services.queue_service import QueueService
from app.utils.security import get_current_active_user


# Create router with /submissions prefix
router = APIRouter(prefix="/submissions", tags=["Submissions"])


@router.post("/structure", response_model=SubmissionStructureResponse)
async def structure_freeform_text(
    request: SubmissionStructureRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Structure freeform text into a structured idea format using AI.

    This endpoint takes natural language input and uses Claude API
    to structure it into what/why/use_case format, adapted to the
    specific product context.

    This is a protected endpoint - requires authentication.

    Args:
        request: Freeform text and product ID from user
        current_user: Authenticated user
        db: Database session

    Returns:
        Structured idea with title, what, why, use_case

    Raises:
        404 Not Found: If product doesn't exist
        500 Internal Server Error: If AI processing fails
    """
    try:
        # Fetch product to get context
        product = db.query(CIProduct).filter(CIProduct.id == request.product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with id {request.product_id} not found"
            )

        # Get product context (similar to idea generation)
        from app.models.competitor_intelligence import ProductFeature

        product_context = {
            'product_name': product.product_name,
            'product_description': product.product_description,
            'product_category': product.product_category
        }

        # Add structured product data if available
        if product.structured_product_data:
            product_context.update({
                'core_features': product.structured_product_data.get('core_features', []),
                'target_users': product.structured_product_data.get('target_users', ''),
                'value_propositions': product.structured_product_data.get('value_propositions', [])
            })

        # Add detailed features for duplicate detection
        if product.analysis_version:
            detailed_features = db.query(ProductFeature).filter(
                ProductFeature.product_id == product.id,
                ProductFeature.analysis_version == product.analysis_version,
                ProductFeature.status == "active"
            ).all()

            product_context['detailed_features'] = [
                {
                    'feature_name': feat.feature_name,
                    'feature_description': feat.feature_description,
                    'feature_category': feat.feature_category
                }
                for feat in detailed_features
            ]

        # Call LLM service to structure the text with product context
        structured_data = llm_service.structure_idea(
            freeform_text=request.freeform_text,
            product_context=product_context
        )

        # Return structured response
        return SubmissionStructureResponse(
            title=structured_data["title"],
            what_description=structured_data["what_description"],
            why_description=structured_data["why_description"],
            use_case_description=structured_data["use_case_description"],
            processing_time=structured_data["processing_time"]
        )

    except HTTPException:
        raise
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
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Submit a complete idea with tracking.

    This endpoint creates both an Idea record and a Submission record
    to track the original freeform text and AI processing details.

    This is a protected endpoint - requires authentication.
    All authenticated users (VOTER, PRODUCT_OWNER, ADMIN) can submit ideas.

    Args:
        submission_data: Complete submission with original text and structured data
        current_user: Authenticated user
        db: Database session

    Returns:
        Created idea and submission information

    Raises:
        400 Bad Request: If data validation fails
        404 Not Found: If product doesn't exist
    """
    # Validate product exists
    product = db.query(CIProduct).filter(CIProduct.id == submission_data.product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {submission_data.product_id} not found"
        )

    # Note: All authenticated users (VOTER, PRODUCT_OWNER, ADMIN) can submit ideas for any product
    # Product permissions are only enforced for product management operations, not idea submission

    # Create the idea first with PENDING triage status
    new_idea = Idea(
        title=submission_data.title,
        what_description=submission_data.what_description,
        why_description=submission_data.why_description,
        use_case_description=submission_data.use_case_description,
        category=submission_data.category,
        product_id=submission_data.product_id,
        source_type=SourceType.CUSTOMER_SUBMISSION,
        submitter_id=current_user.id,
        status=IdeaStatus.PENDING,
        is_active=False,  # Will be set to True when ACCEPTED
    )

    db.add(new_idea)
    db.flush()  # Get the idea ID without committing

    # Create initial status history record
    initial_status = IdeaStatusHistory(
        idea_id=new_idea.id,
        previous_status=None,  # First status
        new_status=IdeaStatus.PENDING,
        changed_by_user_id=current_user.id,
        is_automated=False,
        change_source='submission',
        comment=None  # No comment for system status transitions
    )
    db.add(initial_status)

    # Generate and store embedding for vector similarity search
    if request and hasattr(request.app.state, 'embedding_model') and request.app.state.embedding_model:
        try:
            # Combine title + what + why for embedding (exclude use_case for brevity)
            combined_text = f"{new_idea.title}. {new_idea.what_description} {new_idea.why_description}"

            # Generate embedding using SentenceTransformer model
            embedding = request.app.state.embedding_model.encode(
                combined_text,
                show_progress_bar=False
            )

            # Store embedding in database (database-agnostic via VectorService)
            VectorService.store_embedding(
                db=db,
                idea_id=new_idea.id,
                embedding=embedding.tolist()
            )
            print(f"✓ Stored embedding for idea {new_idea.id}")
        except Exception as e:
            # Log warning but don't fail submission
            print(f"Warning: Failed to generate/store embedding for idea {new_idea.id}: {e}")
            # Continue without embedding - semantic search won't find this idea until migration

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

    # Queue triage job to run agent analysis in background
    try:
        from app.queue.tasks import triage_idea_task

        queue_service = QueueService(db)
        job = queue_service.create_job(
            job_type=JobType.IDEA_TRIAGE,
            input_data={
                'idea_id': new_idea.id,
                'source_type': SourceType.CUSTOMER_SUBMISSION.value,
            },
            product_id=submission_data.product_id,
            user_id=current_user.id,
        )

        # Queue the triage task
        celery_result = triage_idea_task.delay(job.id)
        queue_service.mark_queued(job.id, celery_result.id)
        print(f"✓ Queued triage job {job.id} for idea {new_idea.id}")
    except Exception as e:
        # Log warning but don't fail submission - triage can be run later
        print(f"Warning: Failed to queue triage job for idea {new_idea.id}: {e}")

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
