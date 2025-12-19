"""
Ideas API endpoints.

This file contains all endpoints for managing ideas:
- POST /ideas - Create a new idea
- GET /ideas - List all ideas with vote counts
- GET /ideas/{id} - Get a single idea
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import Optional, List

from app.database import get_db
from app.models.idea import Idea, IdeaStatus, SourceType
from app.models.vote import Vote
from app.models.user import User
from app.models.competitor_intelligence import CIProduct, ProductPermissionLevel
from app.schemas.idea import IdeaCreate, IdeaResponse, IdeaListItem, IdeaListResponse, VoteCount, SimilarIdeaResponse
from app.services.permission_service import PermissionService
from app.services.vector_service import VectorService
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
