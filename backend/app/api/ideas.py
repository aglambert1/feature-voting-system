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
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from app.database import get_db


class IdeaSortOption(str, Enum):
    """Sort options for ideas list."""
    MOST_VOTES = "most_votes"      # Most upvotes first (default for voters)
    PENDING_FIRST = "pending_first"  # Pending/needs_review first, then by votes (default for POs)
    MOST_RECENT = "most_recent"    # Newest first
    MY_IDEAS = "my_ideas"          # User's own ideas first, then by votes
from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.idea_comment import IdeaComment
from app.models.idea_status_history import IdeaStatusHistory
from app.models.vote import Vote
from app.models.user import User, UserRole
from app.models.queue import JobType
from app.models.competitor_intelligence import CIProduct, ProductPermission, ProductPermissionLevel
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
        func.count(Vote.id).label('total_votes')
    ).filter(Vote.idea_id == idea_id).first()

    total = int(result.total_votes or 0)
    return VoteCount(
        upvotes=total,
        total_votes=total
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


@router.post("", response_model=IdeaResponse, status_code=status.HTTP_201_CREATED)
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
    # Create new idea - start as PENDING for triage
    new_idea = Idea(
        title=idea_data.title,
        what_description=idea_data.what_description,
        why_description=idea_data.why_description,
        use_case_description=idea_data.use_case_description,
        category=idea_data.category,
        source_type=SourceType.CUSTOMER_SUBMISSION,
        product_id=idea_data.product_id,
        submitter_id=current_user.id,
        status=IdeaStatus.PENDING,
        is_active=False,  # Will be set to True when ACCEPTED
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
        product_id=new_idea.product_id,
        vote_counts=vote_counts,
        user_vote=None  # New idea, user hasn't voted yet
    )

    return response


@router.get("", response_model=IdeaListResponse)
def list_ideas(
    skip: int = 0,
    limit: int = 100,
    product_id: Optional[int] = None,
    lifecycle_status_id: Optional[int] = None,
    sort_by: Optional[IdeaSortOption] = None,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List ideas with vote counts, optionally filtered by product.

    Visibility rules:
    - ADMIN: See all ideas (active and inactive) for all products
    - PRODUCT_OWNER: See all ideas (active and inactive) for products they own
    - VOTER: See all their own submitted ideas (any status) + only active ideas from others

    Sort options:
    - most_votes: Highest score first (default for voters)
    - pending_first: Pending/needs_review first, then by votes (default for POs)
    - most_recent: Newest first
    - my_ideas: User's own ideas first, then by votes

    Args:
        skip: Number of items to skip (pagination)
        limit: Maximum number of items to return
        product_id: Optional product ID to filter by
        sort_by: Sort order (defaults to pending_first for PO/Admin, most_votes for voters)
        current_user: Current authenticated user (optional for backward compatibility)
        db: Database session

    Returns:
        List of ideas with vote counts

    Raises:
        404 Not Found: If product doesn't exist
    """
    from sqlalchemy import or_, and_

    # Determine user's visibility level
    is_admin = current_user and current_user.role == UserRole.ADMIN
    is_po = current_user and current_user.role == UserRole.PRODUCT_OWNER

    # Get accessible product IDs for PO and VOTER roles
    accessible_product_ids = []
    if is_po and current_user:
        # POs: products they created + explicitly granted
        owned = db.query(CIProduct.id).filter(
            CIProduct.created_by_user_id == current_user.id
        ).all()
        granted = db.query(ProductPermission.product_id).filter(
            ProductPermission.user_id == current_user.id
        ).all()
        accessible_product_ids = list(set(
            [p.id for p in owned] + [p.product_id for p in granted]
        ))
    elif current_user:
        # Voters: only explicitly permitted products
        permitted = db.query(ProductPermission.product_id).filter(
            ProductPermission.user_id == current_user.id
        ).all()
        accessible_product_ids = [p.product_id for p in permitted]

    # Build base query with visibility rules
    if is_admin:
        # Admins see all ideas
        query = db.query(Idea)
    elif is_po and current_user:
        # POs see all ideas for accessible products, plus their own submissions
        query = db.query(Idea).filter(
            or_(
                Idea.product_id.in_(accessible_product_ids),
                Idea.submitter_id == current_user.id,
            )
        )
    elif current_user:
        # Voters see their own ideas (any status) + active ideas from permitted products
        query = db.query(Idea).filter(
            or_(
                Idea.submitter_id == current_user.id,
                and_(Idea.is_active == True, Idea.product_id.in_(accessible_product_ids))
            )
        )
    else:
        # Unauthenticated users see nothing (require auth for beta)
        query = db.query(Idea).filter(Idea.id == -1)  # empty result

    # Filter by product if specified
    if product_id is not None:
        # Validate product exists
        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with id {product_id} not found"
            )

        query = query.filter(Idea.product_id == product_id)

    # Filter by lifecycle status if specified
    if lifecycle_status_id is not None:
        query = query.filter(Idea.lifecycle_status_id == lifecycle_status_id)

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

        # Get duplicate title if exists
        duplicate_title = None
        if idea.duplicate_of_idea_id:
            duplicate_idea = db.query(Idea).filter(Idea.id == idea.duplicate_of_idea_id).first()
            if duplicate_idea:
                duplicate_title = duplicate_idea.title

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
            status=idea.status,
            is_active=idea.is_active,
            duplicate_of_idea_id=idea.duplicate_of_idea_id,
            duplicate_of_title=duplicate_title,
            lifecycle_status_id=idea.lifecycle_status_id,
            lifecycle_status_name=idea.lifecycle_status.name if idea.lifecycle_status else None,
            lifecycle_status_color=idea.lifecycle_status.color if idea.lifecycle_status else None,
            vote_counts=vote_counts,
            user_vote=user_vote,
            user_vote_timestamp=user_vote_timestamp,
            submitter_id=idea.submitter_id
        ))

    # Determine effective sort order
    # Default: pending_first for PO/Admin, most_votes for voters
    effective_sort = sort_by
    if effective_sort is None:
        if is_admin or is_po:
            effective_sort = IdeaSortOption.PENDING_FIRST
        else:
            effective_sort = IdeaSortOption.MOST_VOTES

    # Apply sorting
    if effective_sort == IdeaSortOption.MOST_VOTES:
        # Sort by score (highest first)
        idea_items.sort(key=lambda x: x.vote_counts.upvotes, reverse=True)
    elif effective_sort == IdeaSortOption.PENDING_FIRST:
        # Pending/needs_review first, then by votes
        # Status priority: pending=0, needs_review=1, others=2
        def pending_sort_key(item):
            status_priority = 2  # Default for other statuses
            if item.status == IdeaStatus.PENDING:
                status_priority = 0
            elif item.status == IdeaStatus.NEEDS_REVIEW:
                status_priority = 1
            # Secondary sort by votes (negative for descending)
            return (status_priority, -item.vote_counts.upvotes)
        idea_items.sort(key=pending_sort_key)
    elif effective_sort == IdeaSortOption.MOST_RECENT:
        # Newest first
        idea_items.sort(key=lambda x: x.created_at, reverse=True)
    elif effective_sort == IdeaSortOption.MY_IDEAS:
        # User's own ideas first, then by votes
        user_id = current_user.id if current_user else None
        def my_ideas_sort_key(item):
            is_mine = 0 if item.submitter_id == user_id else 1
            return (is_mine, -item.vote_counts.upvotes)
        idea_items.sort(key=my_ideas_sort_key)

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
    Get active products for idea submission/filtering.

    Returns products scoped by role:
    - ADMIN: all active products
    - PRODUCT_OWNER: products they created + explicitly granted
    - VOTER: only products with explicit ProductPermission

    Returns:
        List of active products with id and product_name
    """
    from sqlalchemy import or_, select

    query = db.query(CIProduct).filter(CIProduct.status == "active")

    if current_user.role == UserRole.ADMIN:
        pass  # no filter
    elif current_user.role == UserRole.PRODUCT_OWNER:
        granted_ids = select(ProductPermission.product_id).where(
            ProductPermission.user_id == current_user.id
        )
        query = query.filter(or_(
            CIProduct.created_by_user_id == current_user.id,
            CIProduct.id.in_(granted_ids)
        ))
    else:
        # VOTER: only explicitly permitted products
        permitted_ids = select(ProductPermission.product_id).where(
            ProductPermission.user_id == current_user.id
        )
        query = query.filter(CIProduct.id.in_(permitted_ids))

    products = query.all()

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
    is_active: bool
    triage_confidence: Optional[float]
    triage_recommendation: Optional[str]
    duplicate_of_idea_id: Optional[int]
    similarity_score: Optional[float]
    auto_response_text: Optional[str]
    created_at: datetime


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
    status_filter: Optional[str] = Query(None, alias="status"),
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

    if status_filter:
        try:
            status_enum = IdeaStatus(status_filter)
            query = query.filter(Idea.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )
    else:
        query = query.filter(Idea.status.in_([
            IdeaStatus.PENDING,
            IdeaStatus.NEEDS_REVIEW,
        ]))

    # Get counts
    total = query.count()
    pending_count = db.query(Idea).filter(
        Idea.product_id == product_id,
        Idea.status == IdeaStatus.PENDING
    ).count()
    needs_review_count = db.query(Idea).filter(
        Idea.product_id == product_id,
        Idea.status == IdeaStatus.NEEDS_REVIEW
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
                is_active=idea.is_active,
                triage_confidence=idea.triage_confidence,
                triage_recommendation=idea.triage_recommendation,
                duplicate_of_idea_id=idea.duplicate_of_idea_id,
                similarity_score=idea.similarity_score,
                auto_response_text=idea.auto_response_text,
                created_at=idea.created_at,
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

    Returns:
        List of similar ideas with similarity scores

    Raises:
        404 Not Found: If product doesn't exist
        500 Internal Server Error: If embedding generation fails
    """
    # Validate product exists and user has access
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    check_product_permission(db, current_user, product_id, ProductPermissionLevel.VIEW)

    # Generate query embedding
    try:
        from app.services.embedding_service import generate_embedding
        query_embedding = generate_embedding(q, input_type="query")
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
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a single idea by ID.

    Requires authentication and product-level VIEW permission.

    Args:
        idea_id: ID of the idea to retrieve
        current_user: Authenticated user
        db: Database session

    Returns:
        Full idea details with vote counts

    Raises:
        403 Forbidden: If user lacks product access
        404 Not Found: If idea doesn't exist
    """
    # Find the idea
    idea = db.query(Idea).filter(Idea.id == idea_id).first()

    if not idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea with id {idea_id} not found"
        )

    # Check product permission
    check_product_permission(db, current_user, idea.product_id, ProductPermissionLevel.VIEW)

    # Get vote counts
    vote_counts = get_vote_counts(db, idea.id)
    user_vote = None

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
        product_id=idea.product_id,
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


class IdeaRespondRequest(BaseModel):
    """Request schema for PO structured response to an idea."""
    status: str = Field(..., description="New status: approved, duplicate, feature_exists, not_appropriate")
    comment: str = Field(..., min_length=1, description="Comment explaining the response")
    duplicate_of_idea_id: Optional[int] = Field(None, description="Required if status is 'duplicate'")


class IdeaCommentRequest(BaseModel):
    """Request schema for adding a comment to an idea."""
    comment_text: str = Field(..., min_length=1, max_length=5000, description="Comment text")


class IdeaCommentResponse(BaseModel):
    """Response schema for a comment."""
    id: int
    idea_id: int
    user_id: int
    username: Optional[str] = None
    comment_text: str
    is_system_generated: bool
    created_at: datetime


class StatusHistoryEntryResponse(BaseModel):
    """Response schema for a status history entry."""
    id: int
    previous_status: Optional[str]
    new_status: Optional[str]
    changed_by_user_id: Optional[int]
    changed_by_username: Optional[str] = None
    is_automated: bool
    change_source: str
    comment: Optional[str]
    confidence: Optional[int]
    created_at: datetime


class IdeaDetailResponse(BaseModel):
    """Extended idea response with comments and triage details."""
    id: int
    title: str
    what_description: str
    why_description: str
    use_case_description: str
    source_type: str
    category: Optional[str]
    status: str
    is_active: bool
    triage_confidence: Optional[float]
    triage_recommendation: Optional[str]
    triage_reasoning: Optional[str]
    duplicate_of_idea_id: Optional[int]
    duplicate_of_title: Optional[str] = None
    similarity_score: Optional[float]
    auto_response_text: Optional[str]
    product_id: int
    product_name: Optional[str] = None
    submitter_id: Optional[int]
    submitter_username: Optional[str] = None
    review_notes: Optional[str]
    reviewer_username: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    comments: List[IdeaCommentResponse] = []
    status_history: List[StatusHistoryEntryResponse] = []
    # Competitive context - only populated for PO/Admin users
    competitive_context: Optional[dict] = None


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
    from app.utils.celery_utils import send_celery_task as send_task

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
        celery_result = send_task('submit_and_triage_idea_task', job.id)
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
    from app.utils.celery_utils import send_celery_task as send_task
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
        celery_result = send_task('submit_and_triage_idea_task', job.id)
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
        'status': idea.status.value,
        'is_active': idea.is_active,
        'triage_confidence': idea.triage_confidence,
        'triage_reasoning': idea.triage_reasoning,
        'triage_recommendation': idea.triage_recommendation,
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

    # Get product for visibility config
    product = db.query(CIProduct).filter(CIProduct.id == idea.product_id).first()
    old_status = idea.status

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

        idea.status = IdeaStatus.DUPLICATE
        idea.duplicate_of_idea_id = request.merge_target_id
        idea.is_active = product.get_is_active_for_status(IdeaStatus.DUPLICATE) if product else False

    elif request.action == 'approve':
        idea.status = IdeaStatus.ACCEPTED
        idea.is_active = product.get_is_active_for_status(IdeaStatus.ACCEPTED) if product else True

    elif request.action == 'reject':
        idea.status = IdeaStatus.NOT_APPROPRIATE
        idea.is_active = product.get_is_active_for_status(IdeaStatus.NOT_APPROPRIATE) if product else False

    # Update review notes
    if request.notes:
        idea.review_notes = request.notes

    # Record status change in history
    status_history = IdeaStatusHistory(
        idea_id=idea.id,
        previous_status=old_status,
        new_status=idea.status,
        changed_by_user_id=current_user.id,
        is_automated=False,
        change_source='po_response',
        comment=request.notes,
    )
    db.add(status_history)

    db.commit()

    return {
        'id': idea.id,
        'title': idea.title,
        'action': request.action,
        'status': idea.status.value,
        'is_active': idea.is_active,
        'reviewed_by': current_user.username,
    }


@router.post("/{idea_id}/publish")
def publish_idea(
    idea_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Publish an idea for voting by setting status to ACCEPTED.

    Idea must be in PENDING or NEEDS_REVIEW status.
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

    # Check status - can publish from PENDING or NEEDS_REVIEW
    if idea.status not in (IdeaStatus.PENDING, IdeaStatus.NEEDS_REVIEW):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Idea cannot be published. Current status: {idea.status.value}"
        )

    # Get product for visibility config
    product = db.query(CIProduct).filter(CIProduct.id == idea.product_id).first()
    old_status = idea.status

    # Set to ACCEPTED
    idea.status = IdeaStatus.ACCEPTED
    idea.is_active = product.get_is_active_for_status(IdeaStatus.ACCEPTED) if product else True

    # Record status change in history
    status_history = IdeaStatusHistory(
        idea_id=idea.id,
        previous_status=old_status,
        new_status=IdeaStatus.ACCEPTED,
        changed_by_user_id=current_user.id,
        is_automated=False,
        change_source='po_response',
        comment="Published for voting",
    )
    db.add(status_history)

    db.commit()

    return {
        'id': idea.id,
        'title': idea.title,
        'status': idea.status.value,
        'is_active': idea.is_active,
        'message': "Idea is now available for voting"
    }


# ============================================================================
# Structured Response Workflow (New Plan Phase 2)
# ============================================================================

def can_respond_to_idea(db: Session, user: User, idea: Idea) -> bool:
    """
    Check if user can respond to an idea.

    Admins can respond to any idea.
    Product Owners can respond to ideas for products they have EDIT permission on.
    """
    if user.role == UserRole.ADMIN:
        return True

    if user.role == UserRole.PRODUCT_OWNER:
        permission_service = PermissionService(db)
        return permission_service.can_access_product(
            user_id=user.id,
            product_id=idea.product_id,
            required_level=ProductPermissionLevel.EDIT
        )

    return False


@router.get("/{idea_id}/detail", response_model=IdeaDetailResponse)
def get_idea_detail(
    idea_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed idea information including comments and triage details.

    Returns full idea details with:
    - Triage recommendation and reasoning
    - All comments
    - Duplicate link info
    - Reviewer info
    """
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea {idea_id} not found"
        )

    # Check product permission
    check_product_permission(db, current_user, idea.product_id, ProductPermissionLevel.VIEW)

    # Get product name
    product_name = None
    product = db.query(CIProduct).filter(CIProduct.id == idea.product_id).first()
    if product:
        product_name = product.product_name

    # Get submitter username
    # For competitor-sourced ideas (no submitter), show source info
    submitter_username = None
    if idea.submitter_id:
        submitter = db.query(User).filter(User.id == idea.submitter_id).first()
        if submitter:
            submitter_username = submitter.username
    elif idea.source_type == SourceType.COMPETITOR_AUTOMATED:
        # For competitor ideas, show source from metadata
        if idea.source_metadata and idea.source_metadata.get('competitor_name'):
            submitter_username = f"From {idea.source_metadata['competitor_name']} analysis"
        else:
            submitter_username = "Competitor analysis"

    # Get duplicate title
    duplicate_of_title = None
    if idea.duplicate_of_idea_id:
        duplicate = db.query(Idea).filter(Idea.id == idea.duplicate_of_idea_id).first()
        if duplicate:
            duplicate_of_title = duplicate.title

    # Get comments with usernames
    comments = []
    for comment in idea.comments:
        user = db.query(User).filter(User.id == comment.user_id).first()
        comments.append(IdeaCommentResponse(
            id=comment.id,
            idea_id=comment.idea_id,
            user_id=comment.user_id,
            username=user.username if user else None,
            comment_text=comment.comment_text,
            is_system_generated=comment.is_system_generated,
            created_at=comment.created_at,
        ))

    # Get status history (most recent first)
    status_history_records = db.query(IdeaStatusHistory).filter(
        IdeaStatusHistory.idea_id == idea_id
    ).order_by(IdeaStatusHistory.created_at.desc()).all()

    status_history = []
    for record in status_history_records:
        changed_by_username = None
        if record.changed_by_user_id:
            changed_by_user = db.query(User).filter(User.id == record.changed_by_user_id).first()
            if changed_by_user:
                changed_by_username = changed_by_user.username

        status_history.append(StatusHistoryEntryResponse(
            id=record.id,
            previous_status=record.previous_status.value if record.previous_status else None,
            new_status=record.new_status.value if record.new_status else None,
            changed_by_user_id=record.changed_by_user_id,
            changed_by_username=changed_by_username,
            is_automated=record.is_automated,
            change_source=record.change_source,
            comment=record.comment,
            confidence=record.confidence,
            created_at=record.created_at,
        ))

    # Competitive context is only shown to PO/Admin users
    is_po_or_admin = current_user.role in [UserRole.ADMIN, UserRole.PRODUCT_OWNER]
    competitive_context = None
    if is_po_or_admin and idea.competitive_context:
        competitive_context = idea.competitive_context

    # Get reviewer info from status history (find last PM review)
    reviewer_username = None
    reviewed_at = None
    for record in status_history_records:
        if record.changed_by_user_id and not record.is_automated:
            changed_by_user = db.query(User).filter(User.id == record.changed_by_user_id).first()
            if changed_by_user:
                reviewer_username = changed_by_user.username
                reviewed_at = record.created_at
            break

    return IdeaDetailResponse(
        id=idea.id,
        title=idea.title,
        what_description=idea.what_description,
        why_description=idea.why_description,
        use_case_description=idea.use_case_description,
        source_type=idea.source_type.value,
        category=idea.category,
        status=idea.status.value,
        is_active=idea.is_active,
        triage_confidence=idea.triage_confidence,
        triage_recommendation=idea.triage_recommendation,
        triage_reasoning=idea.triage_reasoning,
        duplicate_of_idea_id=idea.duplicate_of_idea_id,
        duplicate_of_title=duplicate_of_title,
        similarity_score=idea.similarity_score,
        auto_response_text=idea.auto_response_text,
        product_id=idea.product_id,
        product_name=product_name,
        submitter_id=idea.submitter_id,
        submitter_username=submitter_username,
        review_notes=idea.review_notes,
        reviewer_username=reviewer_username,
        reviewed_at=reviewed_at,
        created_at=idea.created_at,
        updated_at=idea.updated_at,
        comments=comments,
        status_history=status_history,
        competitive_context=competitive_context,
    )


@router.post("/{idea_id}/respond")
def respond_to_idea(
    idea_id: int,
    request: IdeaRespondRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Submit PO structured response to an idea.

    Statuses:
    - approved: Accept the idea for voting (is_active=True)
    - duplicate: Mark as duplicate of another idea (is_active=False)
    - feature_exists: Feature already exists in product (is_active=False)
    - not_appropriate: Inappropriate or off-topic (is_active=False)

    A comment is always required explaining the response.
    For 'duplicate' status, duplicate_of_idea_id is required.

    Only PO of the product or Admin can respond.
    """
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea {idea_id} not found"
        )

    # Check permission
    if not can_respond_to_idea(db, current_user, idea):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the product owner or admin can respond to this idea"
        )

    # Validate status
    valid_statuses = ['approved', 'duplicate', 'feature_exists', 'not_appropriate']
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    # Handle duplicate status with vote transfer
    votes_transferred = 0
    if request.status == 'duplicate':
        if not request.duplicate_of_idea_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="duplicate_of_idea_id is required for 'duplicate' status"
            )

        # Validate duplicate target exists and is in same product
        duplicate_target = db.query(Idea).filter(
            Idea.id == request.duplicate_of_idea_id,
            Idea.product_id == idea.product_id
        ).first()

        if not duplicate_target:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate target idea {request.duplicate_of_idea_id} not found in same product"
            )

        idea.duplicate_of_idea_id = request.duplicate_of_idea_id

        # Transfer votes from duplicate to original idea
        # Get all votes from the duplicate idea
        duplicate_votes = db.query(Vote).filter(Vote.idea_id == idea.id).all()

        # Get users who already voted on the original idea
        original_voter_ids = set(
            v.user_id for v in db.query(Vote).filter(Vote.idea_id == duplicate_target.id).all()
        )

        for vote in duplicate_votes:
            if vote.user_id not in original_voter_ids:
                # Transfer vote: create new vote on original idea
                new_vote = Vote(
                    idea_id=duplicate_target.id,
                    user_id=vote.user_id,
                    vote_value=vote.vote_value,
                )
                db.add(new_vote)
                votes_transferred += 1
            # Delete original vote from duplicate idea
            db.delete(vote)

        # Add system comment to the ORIGINAL idea about the duplicate closure
        duplicate_notification = IdeaComment(
            idea_id=duplicate_target.id,
            user_id=current_user.id,
            comment_text=f"Similar idea \"{idea.title}\" (ID: {idea.id}) was closed as a duplicate of this idea.",
            is_system_generated=True,
        )
        db.add(duplicate_notification)

        # Add system comment about vote transfer if any votes were transferred
        if votes_transferred > 0:
            vote_transfer_comment = IdeaComment(
                idea_id=duplicate_target.id,
                user_id=current_user.id,
                comment_text=f"{votes_transferred} vote(s) transferred from the duplicate idea.",
                is_system_generated=True,
            )
            db.add(vote_transfer_comment)

    # Update status and is_active based on response
    # Get product for visibility config
    product = db.query(CIProduct).filter(CIProduct.id == idea.product_id).first()

    status_map = {
        'approved': IdeaStatus.ACCEPTED,
        'duplicate': IdeaStatus.DUPLICATE,
        'feature_exists': IdeaStatus.FEATURE_EXISTS,
        'not_appropriate': IdeaStatus.NOT_APPROPRIATE,
    }

    previous_status = idea.status
    new_status = status_map[request.status]
    idea.status = new_status
    idea.is_active = product.get_is_active_for_status(new_status) if product else (new_status == IdeaStatus.ACCEPTED)

    idea.review_notes = request.comment

    # Create comment record
    comment = IdeaComment(
        idea_id=idea.id,
        user_id=current_user.id,
        comment_text=request.comment,
        is_system_generated=False,
    )
    db.add(comment)

    # Create status history record
    status_history = IdeaStatusHistory(
        idea_id=idea.id,
        previous_status=previous_status,
        new_status=new_status,
        changed_by_user_id=current_user.id,
        is_automated=False,
        change_source='po_response',
        comment=request.comment,
    )
    db.add(status_history)

    db.commit()

    response = {
        'id': idea.id,
        'title': idea.title,
        'status': idea.status.value,
        'is_active': idea.is_active,
        'duplicate_of_idea_id': idea.duplicate_of_idea_id,
        'responded_by': current_user.username,
    }

    # Include vote transfer info for duplicate responses
    if request.status == 'duplicate':
        response['votes_transferred'] = votes_transferred

    return response


@router.post("/{idea_id}/comments", response_model=IdeaCommentResponse)
def add_comment(
    idea_id: int,
    request: IdeaCommentRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Add a comment to an idea.

    Comments can be added by:
    - Any authenticated user with product access (for active/published ideas)
    - The idea submitter (even for non-published ideas)
    - Product owners with EDIT permission
    - Admins

    Used for discussion and follow-up on ideas.
    """
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea {idea_id} not found"
        )

    # Verify user has VIEW access to the idea's product
    check_product_permission(db, current_user, idea.product_id, ProductPermissionLevel.VIEW)

    # Check permission for non-active ideas
    is_submitter = idea.submitter_id == current_user.id
    is_po_or_admin = can_respond_to_idea(db, current_user, idea)
    is_idea_active = idea.is_active and idea.status == IdeaStatus.ACCEPTED

    # Users with product access can comment on active/accepted ideas
    # Submitter, PO, Admin can comment on any idea
    if not is_idea_active and not is_submitter and not is_po_or_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only comment on active ideas, or if you are the submitter/admin"
        )

    # Create comment
    comment = IdeaComment(
        idea_id=idea.id,
        user_id=current_user.id,
        comment_text=request.comment_text,
        is_system_generated=False,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return IdeaCommentResponse(
        id=comment.id,
        idea_id=comment.idea_id,
        user_id=comment.user_id,
        username=current_user.username,
        comment_text=comment.comment_text,
        is_system_generated=comment.is_system_generated,
        created_at=comment.created_at,
    )


@router.get("/{idea_id}/comments", response_model=List[IdeaCommentResponse])
def get_comments(
    idea_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all comments for an idea.
    """
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea {idea_id} not found"
        )

    # Verify user has VIEW access to the idea's product
    check_product_permission(db, current_user, idea.product_id, ProductPermissionLevel.VIEW)

    comments = []
    for comment in idea.comments:
        user = db.query(User).filter(User.id == comment.user_id).first()
        comments.append(IdeaCommentResponse(
            id=comment.id,
            idea_id=comment.idea_id,
            user_id=comment.user_id,
            username=user.username if user else None,
            comment_text=comment.comment_text,
            is_system_generated=comment.is_system_generated,
            created_at=comment.created_at,
        ))

    return comments


@router.get("/{idea_id}/triage-recommendation")
def get_triage_recommendation(
    idea_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get AI triage recommendation for an idea.

    Returns the agent's suggested response with:
    - Recommended status
    - Confidence score
    - Suggested comment
    - Reasoning
    - Similar ideas found

    Requires EDIT permission on the product (PO or Admin).
    """
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea {idea_id} not found"
        )

    # Check permission
    if not can_respond_to_idea(db, current_user, idea):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the product owner or admin can view triage recommendations"
        )

    # Map triage recommendation to a status using the same classifier the
    # auto-execute path uses. This ensures a `reject` action with an existing
    # feature match surfaces as `feature_exists` to the PM regardless of
    # whether auto-respond was enabled when triage ran.
    recommended_status = None
    if idea.triage_recommendation:
        from app.agents.idea_triage import classify_recommendation
        existing_feature = (idea.competitive_context or {}).get('existing_feature')
        mock_result = {
            'recommendation': {
                'action': idea.triage_recommendation,
                'reasoning': idea.triage_reasoning or '',
                'confidence': float(idea.triage_confidence or 0.5),
            },
            'existing_feature_info': existing_feature,
        }
        recommended_status_enum = classify_recommendation(mock_result)
        status_to_response = {
            IdeaStatus.ACCEPTED: 'approved',
            IdeaStatus.DUPLICATE: 'duplicate',
            IdeaStatus.FEATURE_EXISTS: 'feature_exists',
            IdeaStatus.NOT_APPROPRIATE: 'not_appropriate',
            IdeaStatus.NEEDS_REVIEW: None,
        }
        recommended_status = status_to_response.get(recommended_status_enum)

    # Get similar ideas
    similar_ideas = []
    if idea.duplicate_of_idea_id:
        duplicate = db.query(Idea).filter(Idea.id == idea.duplicate_of_idea_id).first()
        if duplicate:
            similar_ideas.append({
                'id': duplicate.id,
                'title': duplicate.title,
                'similarity_score': idea.similarity_score,
            })

    # Get vote counts and voter names
    votes = db.query(Vote).filter(Vote.idea_id == idea_id).all()

    # Get voter usernames
    voter_ids = [v.user_id for v in votes]
    voters = []
    if voter_ids:
        voter_users = db.query(User).filter(User.id.in_(voter_ids)).all()
        voters = [{'id': u.id, 'username': u.username} for u in voter_users]

    # Get competitive context
    competitive_context = idea.competitive_context or {}
    competitors_with_feature = competitive_context.get('competitors_with_feature', [])
    competitive_urgency = competitive_context.get('competitive_urgency', None)
    existing_feature = competitive_context.get('existing_feature', None)
    # Sanitize source_url at read time too — historical rows persisted before
    # the write-time guard may contain placeholder strings ("N/A") that would
    # render as broken relative URLs in the frontend.
    if isinstance(existing_feature, dict):
        url = existing_feature.get('source_url')
        if isinstance(url, str) and not url.strip().lower().startswith(('http://', 'https://')):
            existing_feature = {**existing_feature, 'source_url': None}

    # Map status to user-facing status for current response
    current_status = None
    if idea.status and idea.status != IdeaStatus.PENDING:
        status_to_response = {
            IdeaStatus.ACCEPTED: 'approved',
            IdeaStatus.DUPLICATE: 'duplicate',
            IdeaStatus.FEATURE_EXISTS: 'feature_exists',
            IdeaStatus.NOT_APPROPRIATE: 'not_appropriate',
            IdeaStatus.MERGED: 'duplicate',
            IdeaStatus.NEEDS_REVIEW: None,
        }
        current_status = status_to_response.get(idea.status)

    # Get status history
    status_history_records = db.query(IdeaStatusHistory).filter(
        IdeaStatusHistory.idea_id == idea_id
    ).order_by(IdeaStatusHistory.created_at.desc()).all()

    status_history = []
    for record in status_history_records:
        # Get user who made the change
        changed_by_username = None
        if record.changed_by_user_id:
            changed_by_user = db.query(User).filter(User.id == record.changed_by_user_id).first()
            if changed_by_user:
                changed_by_username = changed_by_user.username

        status_history.append({
            'id': record.id,
            'previous_status': record.previous_status.value if record.previous_status else None,
            'new_status': record.new_status.value if record.new_status else None,
            'changed_by_user_id': record.changed_by_user_id,
            'changed_by_username': changed_by_username,
            'is_automated': record.is_automated,
            'change_source': record.change_source,
            'comment': record.comment,
            'confidence': record.confidence,
            'created_at': record.created_at.isoformat() if record.created_at else None,
        })

    return {
        'idea_id': idea.id,
        'has_recommendation': idea.triage_recommendation is not None,
        'recommended_status': recommended_status,
        'confidence': idea.triage_confidence,
        'suggested_comment': idea.auto_response_text,
        'reasoning': idea.triage_reasoning,
        'duplicate_of_idea_id': idea.duplicate_of_idea_id,
        'similar_ideas': similar_ideas,
        # Source summary for PO context
        'source_summary': {
            'vote_count': len(votes),
            'voters': voters,
            'competitors_with_feature': competitors_with_feature,
            'competitive_urgency': competitive_urgency,
            # Existing feature match info (from triage analysis)
            'existing_feature': existing_feature,
        },
        # Current response (if already responded) - derived from status history
        'current_response': {
            'status': current_status,
            'comment': idea.review_notes,
            # Get reviewed_at from first non-automated status change
            'reviewed_at': next(
                (h['created_at'] for h in status_history if not h['is_automated'] and h['change_source'] in ('po_response', 'po_edit')),
                None
            ),
        } if current_status else None,
        # Status history for audit trail
        'status_history': status_history,
    }


@router.get("/{idea_id}/can-respond")
def check_can_respond(
    idea_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Check if the current user can respond to an idea.

    Returns whether the user has permission to respond (Edit Response).
    """
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Idea {idea_id} not found"
        )

    can_respond = can_respond_to_idea(db, current_user, idea)

    return {
        'idea_id': idea_id,
        'can_respond': can_respond,
        'product_id': idea.product_id,
    }
