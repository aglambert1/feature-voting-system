"""
Ideas API endpoints.

This file contains all endpoints for managing ideas:
- POST /ideas - Create a new idea
- GET /ideas - List all ideas with vote counts
- GET /ideas/{id} - Get a single idea

Phase 3 additions:
- POST /ideas/submit - Submit idea with AI triage
- POST /ideas/from-feature - Create idea from competitor feature
- GET /ideas/pending-review - List ideas needing PM review
- POST /ideas/{id}/review - PM review action
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.idea import Idea, IdeaStatus, SourceType, TriageStatus, TriageAction
from app.models.vote import Vote
from app.models.user import User
from app.models.queue import JobType
from app.models.competitor_intelligence import CIProduct, ProductPermissionLevel
from app.schemas.idea import IdeaCreate, IdeaResponse, IdeaListItem, IdeaListResponse, VoteCount, SimilarIdeaResponse
from app.services.permission_service import PermissionService
from app.services.vector_service import VectorService
from app.services.queue_service import QueueService
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


def get_user_vote(db: Session, idea_id: int, user_id: Optional[int]) -> tuple[Optional[int], Optional[str]]:
    """
    Get the current user's vote on an idea and when they voted.

    Args:
        db: Database session
        idea_id: ID of the idea
        user_id: ID of the user (None if not authenticated)

    Returns:
        Tuple of (vote value, timestamp) - both None if no vote
    """
    if user_id is None:
        return (None, None)

    vote = db.query(Vote).filter(
        Vote.idea_id == idea_id,
        Vote.user_id == user_id
    ).first()

    if vote:
        return (vote.vote_value, vote.updated_at)
    return (None, None)


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
    product_id: Optional[int] = None,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all active ideas with vote counts, optionally filtered by product.

    This endpoint is accessible to all authenticated users.
    Ideas are sorted by score (highest first).

    Args:
        skip: Number of items to skip (pagination)
        limit: Maximum number of items to return
        product_id: Optional product ID to filter by
        current_user: Current authenticated user (optional for backward compatibility)
        db: Database session

    Returns:
        List of ideas with vote counts

    Raises:
        404 Not Found: If product doesn't exist
    """
    # Build base query for active ideas
    query = db.query(Idea).filter(Idea.status == IdeaStatus.ACTIVE)

    # Filter by product if specified
    if product_id is not None:
        # Validate product exists
        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with id {product_id} not found"
            )

        # Note: All authenticated users can view ideas for any product
        # Product permissions are only enforced for product management operations, not idea viewing

        query = query.filter(Idea.product_id == product_id)

    ideas = query.all()

    # Build list items with vote counts and product info
    idea_items = []
    for idea in ideas:
        vote_counts = get_vote_counts(db, idea.id)

        # Get user's vote and timestamp if authenticated
        user_vote = None
        user_vote_timestamp = None
        if current_user:
            user_vote, user_vote_timestamp = get_user_vote(db, idea.id, current_user.id)

        # Get product name
        product_name = None
        if idea.product_id:
            product = db.query(CIProduct).filter(CIProduct.id == idea.product_id).first()
            if product:
                product_name = product.product_name

        idea_items.append(IdeaListItem(
            id=idea.id,
            title=idea.title,
            what_description=idea.what_description,
            why_description=idea.why_description,
            use_case_description=idea.use_case_description,
            category=idea.category,
            created_at=idea.created_at,
            product_id=idea.product_id,
            product_name=product_name,
            vote_counts=vote_counts,
            user_vote=user_vote,
            user_vote_timestamp=user_vote_timestamp
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


@router.get("/products", response_model=list)
def get_products_for_ideas(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all active products for idea submission/filtering.

    This endpoint returns ALL products to all authenticated users,
    regardless of role. This is used for:
    - Product dropdown on idea submission page
    - Product filter on ideas browsing page

    Product Owners see all products here, but only see their own
    products on the /product-intelligence page.

    Returns:
        List of active products with id and product_name
    """
    products = db.query(CIProduct).filter(CIProduct.status == "active").all()

    return [
        {
            "id": product.id,
            "product_name": product.product_name
        }
        for product in products
    ]


# ============================================================================
# Phase 3 Schema Classes (defined before routes that use them)
# ============================================================================

class TriageIdeaResponse(BaseModel):
    """Response schema for triaged idea."""
    id: int
    title: str
    what_description: str
    why_description: str
    use_case_description: str
    source_type: str
    category: Optional[str]
    status: str
    triage_status: str
    triage_confidence: Optional[float]
    triage_recommendation: Optional[str]
    duplicate_of_idea_id: Optional[int]
    similarity_score: Optional[float]
    auto_response_text: Optional[str]
    published_for_voting: bool
    created_at: datetime
    reviewed_at: Optional[datetime]


class TriageQueueResponse(BaseModel):
    """Response schema for triage queue listing."""
    ideas: List[TriageIdeaResponse]
    total: int
    pending_count: int
    needs_review_count: int


def check_product_permission(
    db: Session,
    user: User,
    product_id: int,
    required_level: ProductPermissionLevel = ProductPermissionLevel.VIEW
) -> CIProduct:
    """Check user has permission for product and return product."""
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )

    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=user.id,
        product_id=product_id,
        required_level=required_level
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have {required_level.value} permission for product {product_id}"
        )

    return product


# ============================================================================
# Phase 3: Idea Pending Review (must be before /{idea_id} catch-all)
# ============================================================================

@router.get("/pending-review", response_model=TriageQueueResponse)
def get_pending_review_list(
    product_id: int = Query(..., description="Product ID to filter by"),
    triage_status_filter: Optional[str] = Query(None, alias="triage_status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List ideas pending PM review.

    Returns ideas that need review along with their triage metadata.
    Requires EDIT permission on the product.
    """
    # Check permission
    check_product_permission(db, current_user, product_id, ProductPermissionLevel.EDIT)

    # Build query
    query = db.query(Idea).filter(Idea.product_id == product_id)

    if triage_status_filter:
        try:
            status_enum = TriageStatus(triage_status_filter)
            query = query.filter(Idea.triage_status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid triage_status: {triage_status_filter}"
            )
    else:
        query = query.filter(Idea.triage_status.in_([
            TriageStatus.PENDING,
            TriageStatus.NEEDS_REVIEW,
        ]))

    # Get counts
    total = query.count()
    pending_count = db.query(Idea).filter(
        Idea.product_id == product_id,
        Idea.triage_status == TriageStatus.PENDING
    ).count()
    needs_review_count = db.query(Idea).filter(
        Idea.product_id == product_id,
        Idea.triage_status == TriageStatus.NEEDS_REVIEW
    ).count()

    # Get ideas with pagination
    ideas = query.order_by(Idea.created_at.desc()).offset(offset).limit(limit).all()

    return TriageQueueResponse(
        ideas=[
            TriageIdeaResponse(
                id=idea.id,
                title=idea.title,
                what_description=idea.what_description,
                why_description=idea.why_description,
                use_case_description=idea.use_case_description,
                source_type=idea.source_type.value,
                category=idea.category,
                status=idea.status.value,
                triage_status=idea.triage_status.value,
                triage_confidence=idea.triage_confidence,
                triage_recommendation=idea.triage_recommendation.value if idea.triage_recommendation else None,
                duplicate_of_idea_id=idea.duplicate_of_idea_id,
                similarity_score=idea.similarity_score,
                auto_response_text=idea.auto_response_text,
                published_for_voting=idea.published_for_voting,
                created_at=idea.created_at,
                reviewed_at=idea.reviewed_at,
            )
            for idea in ideas
        ],
        total=total,
        pending_count=pending_count,
        needs_review_count=needs_review_count,
    )


@router.get("/similar", response_model=List[SimilarIdeaResponse])
async def find_similar_ideas(
    q: str = Query(..., min_length=10, max_length=1000, description="Query text for similarity search"),
    product_id: int = Query(..., description="Product ID to filter by"),
    limit: int = Query(5, ge=1, le=10, description="Maximum number of results to return"),
    threshold: float = Query(0.7, ge=0.0, le=1.0, description="Minimum similarity score"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Find similar ideas using semantic search.

    This endpoint performs vector similarity search to find ideas similar to the query text.
    Used for duplicate detection during idea submission.

    Args:
        q: Query text (min 10 characters)
        product_id: Filter results to this product only
        limit: Maximum number of results (default 5, max 10)
        threshold: Minimum similarity score (0.0-1.0, default 0.7)
        current_user: Authenticated user
        db: Database session
        request: FastAPI request object (to access app.state.embedding_model)

    Returns:
        List of similar ideas with similarity scores

    Raises:
        404 Not Found: If product doesn't exist
        503 Service Unavailable: If embedding model not loaded
        500 Internal Server Error: If embedding generation fails
    """
    # Validate product exists
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )

    # Check if embedding model is available
    if not hasattr(request.app.state, 'embedding_model') or request.app.state.embedding_model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic search unavailable - embedding model not loaded"
        )

    # Generate query embedding
    try:
        query_embedding = request.app.state.embedding_model.encode(
            q,
            show_progress_bar=False
        ).tolist()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding generation failed: {str(e)}"
        )

    # Perform vector similarity search
    try:
        results = VectorService.find_similar(
            db=db,
            query_embedding=query_embedding,
            product_id=product_id,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector search failed: {str(e)}"
        )

    # Convert cosine distance to similarity score and filter by threshold
    # Distance: 0=identical, 1=orthogonal, 2=opposite
    # Similarity: 1=identical, 0=opposite
    similar_ideas = []
    for row in results:
        # row is (idea_id, title, what_description, distance)
        distance = row[3]
        similarity = 1 - (distance / 2)

        if similarity >= threshold:
            similar_ideas.append(SimilarIdeaResponse(
                id=row[0],
                title=row[1],
                what_description=row[2],
                similarity_score=round(similarity, 3)
            ))

    return similar_ideas


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


# ============================================================================
# Phase 3: Idea Submission with AI Triage
# ============================================================================

class IdeaSubmissionRequest(BaseModel):
    """Request schema for submitting an idea with AI triage."""
    product_id: int = Field(..., description="Product ID this idea is for")
    title: Optional[str] = Field(None, max_length=255, description="Idea title (optional for freeform)")
    what_description: Optional[str] = Field(None, description="What is the feature?")
    why_description: Optional[str] = Field(None, description="Why is it valuable?")
    use_case_description: Optional[str] = Field(None, description="How would it be used?")
    freeform_text: Optional[str] = Field(None, description="Freeform idea description (AI will structure)")
    category: Optional[str] = Field(None, max_length=100)


class FeatureToIdeaRequest(BaseModel):
    """Request schema for converting a competitor feature to an idea."""
    product_id: int = Field(..., description="Product ID to create idea for")
    feature_id: int = Field(..., description="Competitor feature ID to convert")
    change_type: Optional[str] = Field(None, description="Type of change (new, modified)")
    change_description: Optional[str] = Field(None, description="Description of what changed")


class JobQueueResponse(BaseModel):
    """Response for queued job."""
    id: int
    job_uuid: str
    job_type: str
    status: str
    product_id: int
    message: str


class PMReviewRequest(BaseModel):
    """Request schema for PM review action."""
    action: str = Field(..., description="Action: approve, reject, merge")
    notes: Optional[str] = Field(None, description="Review notes")
    merge_target_id: Optional[int] = Field(None, description="ID to merge with (for merge action)")
    publish_for_voting: bool = Field(True, description="Publish for voting on approval")


@router.post("/submit", response_model=JobQueueResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_idea_with_triage(
    request: IdeaSubmissionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Submit a new idea for AI-powered triage.

    The idea will be normalized (if freeform), created, and automatically triaged
    for duplicates, category, and competitive context.

    Supports two modes:
    1. Structured: Provide title, what, why, use_case fields
    2. Freeform: Provide freeform_text (AI will structure it)

    Returns a job ID for tracking progress.
    """
    from app.queue.tasks import submit_and_triage_idea_task

    # Check permission (VIEW is sufficient to submit ideas)
    product = check_product_permission(db, current_user, request.product_id, ProductPermissionLevel.VIEW)

    # Validate input
    has_freeform = bool(request.freeform_text and request.freeform_text.strip())
    has_structured = all([
        request.title and request.title.strip(),
        request.what_description and request.what_description.strip(),
        request.why_description and request.why_description.strip(),
        request.use_case_description and request.use_case_description.strip(),
    ])

    if not has_freeform and not has_structured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either freeform_text OR all structured fields (title, what, why, use_case)"
        )

    # Build raw input for normalizer
    raw_input = {
        'product_id': request.product_id,
        'submitter_id': current_user.id,
    }

    if has_freeform:
        raw_input['freeform_text'] = request.freeform_text
    else:
        raw_input['title'] = request.title
        raw_input['what_description'] = request.what_description
        raw_input['why_description'] = request.why_description
        raw_input['use_case_description'] = request.use_case_description

    if request.category:
        raw_input['category'] = request.category

    # Create job
    queue_service = QueueService(db)
    job = queue_service.create_job(
        job_type=JobType.IDEA_NORMALIZATION,
        input_data={
            'raw_input': raw_input,
            'source_type': SourceType.CUSTOMER_SUBMISSION.value,
        },
        product_id=request.product_id,
        user_id=current_user.id,
    )

    # Queue the task
    try:
        celery_result = submit_and_triage_idea_task.delay(job.id)
        queue_service.mark_queued(job.id, celery_result.id)
    except Exception as e:
        queue_service.mark_failure(job.id, f"Failed to queue task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue idea submission: {str(e)}"
        )

    return JobQueueResponse(
        id=job.id,
        job_uuid=job.job_uuid,
        job_type=job.job_type.value,
        status=job.status.value,
        product_id=request.product_id,
        message="Idea submitted. It will be processed and triaged automatically."
    )


@router.post("/from-feature", response_model=JobQueueResponse, status_code=status.HTTP_202_ACCEPTED)
def create_idea_from_feature(
    request: FeatureToIdeaRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create an idea from a competitor feature.

    The competitor feature will be adapted to the product's context
    and automatically triaged.

    Requires EDIT permission on the product.
    """
    from app.queue.tasks import submit_and_triage_idea_task
    from app.models.competitor_intelligence import ProductCompetitorFeature, ProductCompetitor

    # Check permission
    product = check_product_permission(db, current_user, request.product_id, ProductPermissionLevel.EDIT)

    # Verify feature exists
    feature = db.query(ProductCompetitorFeature).filter(
        ProductCompetitorFeature.id == request.feature_id
    ).first()

    if not feature:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feature {request.feature_id} not found"
        )

    # Verify feature belongs to a competitor of this product
    competitor = db.query(ProductCompetitor).filter(
        ProductCompetitor.id == feature.product_competitor_id,
        ProductCompetitor.product_id == request.product_id
    ).first()

    if not competitor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Feature {request.feature_id} does not belong to a competitor of product {request.product_id}"
        )

    # Build raw input
    raw_input = {
        'product_id': request.product_id,
        'feature_id': request.feature_id,
    }

    if request.change_type:
        raw_input['change_type'] = request.change_type
    if request.change_description:
        raw_input['change_description'] = request.change_description

    # Create job
    queue_service = QueueService(db)
    job = queue_service.create_job(
        job_type=JobType.IDEA_NORMALIZATION,
        input_data={
            'raw_input': raw_input,
            'source_type': SourceType.COMPETITOR_AUTOMATED.value,
        },
        product_id=request.product_id,
        user_id=current_user.id,
    )

    # Queue the task
    try:
        celery_result = submit_and_triage_idea_task.delay(job.id)
        queue_service.mark_queued(job.id, celery_result.id)
    except Exception as e:
        queue_service.mark_failure(job.id, f"Failed to queue task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue feature-to-idea conversion: {str(e)}"
        )

    return JobQueueResponse(
        id=job.id,
        job_uuid=job.job_uuid,
        job_type=job.job_type.value,
        status=job.status.value,
        product_id=request.product_id,
        message=f"Converting feature '{feature.feature_name}' to idea."
    )


@router.get("/{idea_id}/triage-details")
def get_idea_triage_details(
    idea_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed triage information for an idea.

    Includes full reasoning, similar ideas, and competitive context.
    Requires EDIT permission on the product.
    """
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea {idea_id} not found"
        )

    # Check permission
    check_product_permission(db, current_user, idea.product_id, ProductPermissionLevel.EDIT)

    # Get duplicate info if set
    similar_ideas = []
    if idea.duplicate_of_idea_id:
        duplicate = db.query(Idea).filter(Idea.id == idea.duplicate_of_idea_id).first()
        if duplicate:
            similar_ideas.append({
                'id': duplicate.id,
                'title': duplicate.title,
                'similarity_score': idea.similarity_score,
                'is_duplicate': True,
            })

    return {
        'idea_id': idea.id,
        'title': idea.title,
        'triage_status': idea.triage_status.value,
        'triage_confidence': idea.triage_confidence,
        'triage_reasoning': idea.triage_reasoning,
        'triage_recommendation': idea.triage_recommendation.value if idea.triage_recommendation else None,
        'category': idea.category,
        'auto_categorized': idea.auto_categorized,
        'duplicate_of_idea_id': idea.duplicate_of_idea_id,
        'similarity_score': idea.similarity_score,
        'similar_ideas': similar_ideas,
        'competitive_context': idea.competitive_context,
        'auto_response_text': idea.auto_response_text,
        'source_metadata': idea.source_metadata,
    }


@router.post("/{idea_id}/review")
def review_idea(
    idea_id: int,
    request: PMReviewRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Submit PM review decision for an idea.

    Actions:
    - approve: Approve the idea (optionally publish for voting)
    - reject: Reject the idea
    - merge: Mark as duplicate and merge with another idea

    Requires EDIT permission on the product.
    """
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea {idea_id} not found"
        )

    # Check permission
    check_product_permission(db, current_user, idea.product_id, ProductPermissionLevel.EDIT)

    # Validate action
    valid_actions = ['approve', 'reject', 'merge']
    if request.action not in valid_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action. Must be one of: {valid_actions}"
        )

    # Handle merge action
    if request.action == 'merge':
        if not request.merge_target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="merge_target_id required for merge action"
            )

        merge_target = db.query(Idea).filter(
            Idea.id == request.merge_target_id,
            Idea.product_id == idea.product_id
        ).first()

        if not merge_target:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Merge target idea {request.merge_target_id} not found in same product"
            )

        idea.triage_status = TriageStatus.DUPLICATE
        idea.duplicate_of_idea_id = request.merge_target_id
        idea.status = IdeaStatus.MERGED

    elif request.action == 'approve':
        idea.triage_status = TriageStatus.APPROVED
        if request.publish_for_voting:
            idea.published_for_voting = True

    elif request.action == 'reject':
        idea.triage_status = TriageStatus.REJECTED

    # Update review metadata
    idea.reviewed_by_user_id = current_user.id
    idea.reviewed_at = datetime.utcnow()
    if request.notes:
        idea.review_notes = request.notes

    db.commit()

    return {
        'id': idea.id,
        'title': idea.title,
        'action': request.action,
        'triage_status': idea.triage_status.value,
        'published_for_voting': idea.published_for_voting,
        'reviewed_by': current_user.username,
        'reviewed_at': idea.reviewed_at.isoformat(),
    }


@router.post("/{idea_id}/publish")
def publish_idea(
    idea_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Publish an approved idea for voting.

    Idea must be in APPROVED or AUTO_APPROVED status.
    Requires EDIT permission on the product.
    """
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea {idea_id} not found"
        )

    # Check permission
    check_product_permission(db, current_user, idea.product_id, ProductPermissionLevel.EDIT)

    # Check status
    if idea.triage_status not in (TriageStatus.APPROVED, TriageStatus.AUTO_APPROVED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Idea must be approved before publishing. Current status: {idea.triage_status.value}"
        )

    idea.published_for_voting = True
    db.commit()

    return {
        'id': idea.id,
        'title': idea.title,
        'published_for_voting': True,
        'message': "Idea is now available for voting"
    }
