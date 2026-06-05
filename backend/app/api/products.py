"""
Products API endpoints for Competitor Intelligence.

This module provides REST API endpoints for managing CI products independently
of analysis sessions. Products are shared team resources with permission-based access.

Independent Stages:
- Stage 0: Create Product (no analysis)
- Stage 1: Analyze Product (independent, can be run multiple times)
- Stage 2: Discover Competitors (handled by sessions)
- Stage 3: Analyze Competitor Features (handled by sessions)
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
import uuid
from pathlib import Path

from app.database import get_db
from app.models.user import User
from app.models.competitor_intelligence import ProductPermissionLevel, CIProduct
from app.models.queue import QueueJob, JobType, JobStatus
from app.services.product_service import ProductService
from app.services.queue_service import QueueService
from app.services.llm_service import llm_service
from app.services.document_parsing_service import DocumentParsingService
from app.utils.security import get_current_active_user, get_product_owner_or_admin

# Thread-safe task dispatch (see app/utils/celery_utils.py for explanation)
from app.utils.celery_utils import send_celery_task as send_task


# Create router with /product-intelligence/products prefix
router = APIRouter(
    prefix="/product-intelligence/products",
    tags=["Product Intelligence - Products"]
)


# ============================================================================
# Request/Response Schemas
# ============================================================================

class ProductCreateRequest(BaseModel):
    """Schema for creating a new product (without analysis)."""
    product_name: str = Field(..., min_length=1, max_length=255)
    product_description: str = Field(..., min_length=10)
    source_type: str = Field(default="text", pattern="^(text|document|url)$")
    source_data: Optional[dict] = None


class ProductUpdateRequest(BaseModel):
    """Schema for updating a product."""
    product_name: Optional[str] = Field(None, min_length=1, max_length=255)
    product_description: Optional[str] = Field(None, min_length=10)


class ProductResponse(BaseModel):
    """Schema for returning product information."""
    id: int
    product_name: str
    product_description: str
    product_category: Optional[str]
    structured_product_data: Optional[dict]
    product_source_type: str
    product_source_data: Optional[dict]
    analysis_version: int
    last_analyzed_at: Optional[datetime]
    analysis_count: int
    created_by_user_id: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Feature Query Schemas
# ============================================================================

class FeatureQueryRequest(BaseModel):
    """Schema for querying product features."""
    query: str = Field(..., min_length=10, max_length=1000, description="Feature description to search for")
    include_similar: bool = Field(default=True, description="Include similar features below threshold")
    similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0, description="Similarity threshold for exact match")


class MatchedFeature(BaseModel):
    """Schema for a matched product feature."""
    feature_name: str
    feature_description: str
    similarity_score: float
    source_url: Optional[str] = None
    is_core_feature: bool = False  # True if from structured_product_data.core_features


class FeatureQueryResponse(BaseModel):
    """Schema for feature query response."""
    query: str
    feature_exists: bool  # True if best_match.similarity_score >= threshold
    confidence: float  # Best match similarity score
    response_text: str  # LLM-generated conversational response
    matched_features: List[MatchedFeature]  # Matches >= threshold
    similar_features: List[MatchedFeature]  # Matches between 0.5 and threshold


# ============================================================================
# Product CRUD Endpoints
# ============================================================================

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    request: ProductCreateRequest,
    current_user: User = Depends(get_product_owner_or_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new product WITHOUT automatic analysis (Stage 0).

    Requires: PRODUCT_OWNER or ADMIN role.

    Products are created as team resources. The creator gets implicit OWNER access.
    Other users can be granted VIEW/EDIT/OWNER permissions separately.

    After creation, use POST /products/{id}/analyze to analyze the product.

    Returns:
        Created product with analysis_version=0 (not yet analyzed)

    Raises:
        403: If user is not a Product Owner or Admin
        400: If product name already exists
    """
    service = ProductService(db)

    try:
        product = service.create_product(
            product_name=request.product_name,
            product_description=request.product_description,
            created_by_user_id=current_user.id,
            source_type=request.source_type,
            source_data=request.source_data
        )
        return product
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("", response_model=List[ProductResponse])
def list_products(
    permission_level: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List all products accessible to the current user.

    Note: This endpoint is accessible to all authenticated users (including VOTER role)
    so they can see product names in dropdown for idea submission. However, the list
    returned is filtered based on role and permissions (see permission_service.py).

    Returns products based on:
    - User's role (VOTER sees all product names, PRODUCT_OWNER sees only their products, ADMIN sees all)
    - User's default_product_access mode (SINGLE_USER vs TEAM_WIDE)
    - Explicit product permission grants

    Args:
        permission_level: Filter by minimum permission level (view, edit, owner)

    Returns:
        List of products the user can access
    """
    service = ProductService(db)

    # Convert string to enum if provided
    perm_level = None
    if permission_level:
        try:
            perm_level = ProductPermissionLevel(permission_level.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permission level. Must be: view, edit, or admin"
            )

    products = service.list_products(
        user_id=current_user.id,
        permission_level=perm_level
    )

    return products


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a product by ID (detail view).

    Requires VIEW permission on the product.

    Returns:
        Product details

    Raises:
        403: If user lacks VIEW permission
        404: If product not found
    """
    service = ProductService(db)
    product = service.get_product(product_id, current_user.id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or you don't have permission to view it"
        )

    return product


@router.get("/{product_id}/analysis-history", response_model=List[dict])
def get_analysis_history(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get analysis history for a product.

    Shows all past analyses, allowing you to see how the product
    analysis has evolved over time.

    Requires VIEW permission on the product.

    Returns:
        List of analysis history records (newest first)

    Raises:
        403: If user lacks VIEW permission
        404: If product not found
    """
    service = ProductService(db)

    try:
        history = service.get_analysis_history(product_id, current_user.id)
        return [
            {
                "id": h.id,
                "analysis_version": h.analysis_version,
                "analyzed_by_user_id": h.analyzed_by_user_id,
                "product_description": h.product_description,
                "product_source_type": h.product_source_type,
                "product_source_data": h.product_source_data,
                "analyzed_structure": h.analyzed_structure,
                "tokens_used": h.tokens_used,
                "created_at": h.created_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ') if h.created_at else None
            }
            for h in history
        ]
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/{product_id}/detailed-features", response_model=List[dict])
def get_detailed_features(
    product_id: int,
    analysis_version: Optional[int] = Query(None, description="Analysis version (default: latest)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed product features for a specific analysis version.

    Returns the granular feature list (10-25 features) that complements
    the core_features (5-7 strategic features) in the analysis structure.

    Requires VIEW permission on the product.

    Args:
        product_id: Product ID
        analysis_version: Specific analysis version (default: latest)

    Returns:
        List of detailed features with metadata

    Raises:
        403: If user lacks VIEW permission
        404: If product or analysis version not found
    """
    from app.models.competitor_intelligence import ProductFeature, CIProduct
    from app.services.permission_service import PermissionService

    # Check permission
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.VIEW
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have VIEW permission for product {product_id}"
        )

    # Get product
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )

    # Use latest version if not specified
    if analysis_version is None:
        analysis_version = product.analysis_version

    # Get detailed features
    features = db.query(ProductFeature).filter(
        ProductFeature.product_id == product_id,
        ProductFeature.analysis_version == analysis_version,
        ProductFeature.status == 'active'
    ).order_by(ProductFeature.feature_category, ProductFeature.feature_name).all()

    if not features:
        return []

    return [
        {
            "id": f.id,
            "feature_name": f.feature_name,
            "feature_description": f.feature_description,
            "feature_category": f.feature_category,
            "extraction_confidence": float(f.extraction_confidence) if f.extraction_confidence else None,
            "source_reference": f.source_reference,
            "created_at": f.created_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ') if f.created_at else None
        }
        for f in features
    ]


@router.post("/{product_id}/feature-query", response_model=FeatureQueryResponse)
def query_product_features(
    product_id: int,
    request: FeatureQueryRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Query if a feature exists in the product.

    Uses the EXACT same similarity detection logic as the Idea Triage Agent,
    ensuring consistent results between:
    - Asking "Does feature X exist?" via this endpoint
    - Submitting an idea for feature X (triage will detect if it exists)

    This endpoint searches:
    1. ProductFeature table (detailed features with embeddings)
    2. core_features from structured_product_data

    Requires VIEW permission on the product.

    Args:
        product_id: Product ID to search within
        request: Query parameters including feature description

    Returns:
        FeatureQueryResponse with:
        - feature_exists: True if similarity >= threshold
        - confidence: Best match similarity score
        - response_text: AI-generated explanation
        - matched_features: Features meeting threshold
        - similar_features: Features between 0.5 and threshold

    Raises:
        400: If product not analyzed
        403: If user lacks VIEW permission
        404: If product not found
    """
    from app.services.permission_service import PermissionService
    from app.services.similarity_detector import SimilarityDetectorService

    # Check permission
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.VIEW
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have VIEW permission for product {product_id}"
        )

    # Get product
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )

    # Check product is analyzed
    if not product.structured_product_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product {product_id} must be analyzed before feature queries"
        )

    # Use EXACT same method as triage_idea_task (tasks.py:878)
    similarity_service = SimilarityDetectorService(db)
    product_feature_result = similarity_service.find_product_feature_matches(
        idea_text=request.query,  # Same parameter name as triage
        product_id=product_id,
        similarity_threshold=request.similarity_threshold,
        limit=5
    )

    # Convert matches to response format
    matched_features = []
    for match in product_feature_result.matches:
        matched_features.append(MatchedFeature(
            feature_name=match.feature_name,
            feature_description=match.feature_description,
            similarity_score=match.similarity_score,
            source_url=match.source_url,
            is_core_feature=(match.feature_id == 0)  # Core features have ID=0
        ))

    # Get similar features below threshold if requested
    similar_features = []
    if request.include_similar:
        # Get features with lower threshold
        similar_result = similarity_service.find_product_feature_matches(
            idea_text=request.query,
            product_id=product_id,
            similarity_threshold=0.5,  # Lower threshold for "similar"
            limit=10
        )

        # Filter to only features between 0.5 and the main threshold
        # (exclude ones already in matched_features)
        matched_names = {m.feature_name.lower() for m in matched_features}
        for match in similar_result.matches:
            if (match.similarity_score < request.similarity_threshold and
                match.feature_name.lower() not in matched_names):
                similar_features.append(MatchedFeature(
                    feature_name=match.feature_name,
                    feature_description=match.feature_description,
                    similarity_score=match.similarity_score,
                    source_url=match.source_url,
                    is_core_feature=(match.feature_id == 0)
                ))

    # Determine if feature exists (same logic as triage)
    feature_exists = product_feature_result.has_match

    # Get confidence as the highest match score (regardless of threshold)
    # This ensures we always show the best match percentage, not 0%
    if product_feature_result.best_match:
        confidence = product_feature_result.best_match.similarity_score
    elif similar_features:
        # No match above threshold, but we have similar features - use highest similar
        confidence = max(f.similarity_score for f in similar_features)
    else:
        confidence = 0.0

    # Collect everything needed before the DB session is used by the LLM call.
    # _generate_feature_query_response makes a synchronous Claude API call that
    # can take 5-30s. Passing db here would hold the connection open for that
    # entire duration, risking pool exhaustion under concurrent requests.
    product_name = product.product_name
    product_category = product.structured_product_data.get('product_category', '')
    db.close()

    # Generate conversational response using LLM (no DB session held)
    response_text = _generate_feature_query_response(
        product_name=product_name,
        product_category=product_category,
        query=request.query,
        feature_exists=feature_exists,
        confidence=confidence,
        matched_features=matched_features,
        similar_features=similar_features,
    )

    return FeatureQueryResponse(
        query=request.query,
        feature_exists=feature_exists,
        confidence=confidence,
        response_text=response_text,
        matched_features=matched_features,
        similar_features=similar_features
    )


def _generate_feature_query_response(
    product_name: str,
    product_category: str,
    query: str,
    feature_exists: bool,
    confidence: float,
    matched_features: List[MatchedFeature],
    similar_features: List[MatchedFeature],
) -> str:
    """
    Generate a conversational response for the feature query.

    Uses LLM to create a helpful, natural language response explaining
    whether the feature exists and providing context.
    """
    # Build context for LLM
    if feature_exists and matched_features:
        matches_text = "\n".join([
            f"- {m.feature_name} (similarity: {m.similarity_score:.0%}): {m.feature_description}"
            for m in matched_features[:3]
        ])
        context = f"MATCHING FEATURES FOUND:\n{matches_text}"
    elif similar_features:
        similar_text = "\n".join([
            f"- {m.feature_name} (similarity: {m.similarity_score:.0%}): {m.feature_description}"
            for m in similar_features[:3]
        ])
        context = f"NO EXACT MATCH, BUT SIMILAR FEATURES FOUND:\n{similar_text}"
    else:
        context = "NO MATCHING OR SIMILAR FEATURES FOUND"

    system_prompt = """You are a product knowledge assistant. Given a user's feature query and search results,
provide a helpful response that:
1. Clearly states whether the feature exists or not
2. If it exists, briefly describes the matching feature(s)
3. If not, mention any similar features that might be relevant
4. Keep responses concise (2-4 sentences)

Be direct and informative. Don't use phrases like "Based on my search" - just state the facts."""

    user_prompt = f"""Product: {product_name}
Category: {product_category}

User Query: "{query}"

Search Results:
{context}

Feature Exists: {feature_exists}
Confidence: {confidence:.0%}

Provide a helpful response about whether this feature exists in {product_name}."""

    try:
        result = llm_service.call_agent(
            agent_name="feature_query_responder",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=300
        )
        return result["content"].strip()
    except Exception as e:
        print(f"[API] Error generating feature query response: {e}")
        # Fallback to simple response if LLM fails
        if feature_exists:
            return f"Yes, {product_name} has this feature: {matched_features[0].feature_name}."
        elif similar_features:
            return f"This exact feature wasn't found, but {product_name} has similar capabilities like {similar_features[0].feature_name}."
        else:
            return f"This feature was not found in {product_name}'s documented capabilities."


@router.get("/{product_id}/source-status")
def check_product_source_status(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Check if product sources have changed since last analysis.

    Returns source change status to detect when product information
    is stale and requires re-analysis before starting new workflows.

    Requires VIEW permission on the product.

    Args:
        product_id: Product ID

    Returns:
        dict with:
        - sources_changed: Boolean indicating if sources have changed
        - last_analyzed_at: When product was last analyzed
        - analysis_version: Current analysis version

    Raises:
        403: If user lacks VIEW permission
        404: If product not found
    """
    service = ProductService(db)
    product = service.get_product(product_id, current_user.id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or you don't have permission to view it"
        )

    # Calculate current source hash
    current_hash = service._calculate_source_hash(
        product_description=product.product_description,
        source_type=product.product_source_type,
        source_data=product.product_source_data
    )

    # Compare to stored hash
    sources_changed = (
        product.last_source_hash is not None and
        current_hash != product.last_source_hash
    )

    return {
        "sources_changed": sources_changed,
        "last_analyzed_at": product.last_analyzed_at.isoformat() if product.last_analyzed_at else None,
        "analysis_version": product.analysis_version
    }


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    request: ProductUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update product information.

    This does NOT trigger re-analysis. Use POST /products/{id}/analyze
    to re-analyze after making changes.

    Requires EDIT permission on the product.

    Returns:
        Updated product

    Raises:
        400: If validation fails (e.g., duplicate name)
        403: If user lacks EDIT permission
        404: If product not found
    """
    service = ProductService(db)

    try:
        product = service.update_product(
            product_id=product_id,
            user_id=current_user.id,
            product_name=request.product_name,
            product_description=request.product_description
        )
        return product
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )


@router.get("/{product_id}/scoring-weights")
def get_scoring_weights(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get effective scoring weights for synthesis priority scoring.

    Returns the merged result of product-specific overrides and defaults.
    Any weight category not overridden by the product uses the default value.

    Requires VIEW permission on the product.
    """
    from app.services.scoring_defaults import get_weights_for_product, DEFAULT_SCORING_WEIGHTS, VOTE_THRESHOLDS

    service = ProductService(db)
    try:
        product = service.get_product(product_id, current_user.id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    effective = get_weights_for_product(product)

    return {
        "product_id": product_id,
        "effective_weights": effective,
        "has_custom_weights": product.scoring_weights is not None,
        "custom_overrides": product.scoring_weights,
        "defaults": DEFAULT_SCORING_WEIGHTS,
        "vote_thresholds": VOTE_THRESHOLDS,
    }


@router.put("/{product_id}/scoring-weights")
def update_scoring_weights(
    product_id: int,
    weights: dict = Body(..., examples=[{
        "source_count": {"three": 40, "two": 25, "one": 10},
        "competitive_prevalence": {"table_stakes": 20, "emerging": 15, "differentiator": 10},
        "customer_votes": {"high": 20, "medium": 15, "low": 10},
        "internal_signal": {"high": 20, "medium": 10},
        "confidence_bonus": 10
    }]),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Set custom scoring weights for synthesis priority scoring.

    Accepts partial overrides — only the keys you include will be customized.
    Unspecified keys will use default values during synthesis.

    Send an empty object {} or null to reset to defaults.

    Requires EDIT permission on the product.
    """
    from app.services.scoring_defaults import get_weights_for_product, DEFAULT_SCORING_WEIGHTS

    service = ProductService(db)
    try:
        product = service.get_product(product_id, current_user.id)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Check EDIT permission
    from app.services.permission_service import PermissionService
    perm_service = PermissionService(db)
    if not perm_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.EDIT
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EDIT permission required to modify scoring weights"
        )

    # Validate weight values are reasonable
    valid_top_keys = set(DEFAULT_SCORING_WEIGHTS.keys())
    for key in weights:
        if key not in valid_top_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown weight category: {key}. Valid: {sorted(valid_top_keys)}"
            )
        if isinstance(weights[key], dict):
            for sub_key, val in weights[key].items():
                if not isinstance(val, (int, float)) or val < 0 or val > 100:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Weight value {key}.{sub_key} must be a number between 0 and 100"
                    )
        elif isinstance(weights[key], (int, float)):
            if weights[key] < 0 or weights[key] > 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Weight value {key} must be a number between 0 and 100"
                )

    # Store overrides (empty dict or None resets to defaults)
    product.scoring_weights = weights if weights else None
    db.commit()

    effective = get_weights_for_product(product)
    return {
        "product_id": product_id,
        "effective_weights": effective,
        "has_custom_weights": product.scoring_weights is not None,
        "custom_overrides": product.scoring_weights,
    }


@router.get("/{product_id}/delete-preview")
def get_delete_preview(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Preview what would be deleted if this product were removed.

    Returns counts of related rows, file paths, and embedding counts
    without making any changes. Requires OWNER permission.
    """
    from app.services.permission_service import PermissionService
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.OWNER
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User {current_user.id} does not have OWNER permission for product {product_id}"
        )

    service = ProductService(db)
    preview = service.get_delete_preview(product_id)
    if preview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    return preview


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    dry_run: bool = Query(False, description="Preview deletion without making changes"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a product and all associated data (hard delete).

    Deletes all related data including:
    - Competitors and their features
    - Analysis sessions and reports
    - Ideas, votes, and submissions
    - Synthesis runs and opportunities
    - Internal feedback imports
    - Vector embeddings
    - File-based competitive reports

    Preserves (with null product_id):
    - Queue job history
    - LLM usage/cost logs
    - Agent execution logs

    Use `?dry_run=true` to preview what would be deleted.
    Requires OWNER permission on the product.
    """
    service = ProductService(db)

    try:
        result = service.delete_product(product_id, current_user.id, dry_run=dry_run)
        if result is False:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        if dry_run:
            return result
        return None
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


# ============================================================================
# Document Upload & URL Fetching Endpoints
# ============================================================================

@router.post("/upload-document")
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload and parse a document (PDF, DOCX, TXT, MD).

    Supported formats: .pdf, .docx, .txt, .md
    Maximum size: 50MB

    The file is saved to temporary storage and parsed to extract text.
    The extracted text is returned immediately for frontend preview.
    Files are moved to permanent storage when the product is created/analyzed.

    Requires: Any authenticated user

    Returns:
        {
            'file_id': str (UUID for tracking),
            'filename': str,
            'file_type': str (extension),
            'extracted_text': str,
            'size_mb': float,
            'token_estimate': int
        }

    Raises:
        400: If file validation fails or parsing fails
        500: If unexpected error occurs
    """
    parsing_service = DocumentParsingService()

    # Validate file
    validation = parsing_service.validate_file(file)
    if not validation['valid']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation['error']
        )

    # Generate unique file ID
    file_id = str(uuid.uuid4())
    file_ext = validation['file_type']
    safe_filename = f"{file_id}_{file.filename}"

    # Create temp directory if it doesn't exist
    temp_dir = Path("uploads/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Save file to temp location
    temp_path = temp_dir / safe_filename
    try:
        with open(temp_path, 'wb') as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )

    # Parse document based on type
    try:
        if file_ext == '.pdf':
            extracted_text = parsing_service.parse_pdf(str(temp_path))
        elif file_ext == '.docx':
            extracted_text = parsing_service.parse_docx(str(temp_path))
        elif file_ext in ['.txt', '.md']:
            extracted_text = parsing_service.parse_text_file(str(temp_path))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_ext}"
            )
    except Exception as e:
        # Clean up temp file on parse failure
        temp_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse document: {str(e)}"
        )

    # Calculate token estimate
    token_estimate = parsing_service.count_tokens_estimate(extracted_text)

    return {
        'file_id': file_id,
        'filename': file.filename,
        'file_type': file_ext,
        'extracted_text': extracted_text,
        'size_mb': round(validation['size_mb'], 2),
        'token_estimate': token_estimate
    }


@router.post("/fetch-url")
async def fetch_url(
    url: str = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user)
):
    """
    Fetch and extract content from a URL.

    Fetches HTML content and extracts main text using BeautifulSoup.
    Converts HTML to clean markdown-style text for better readability.

    Security features:
    - SSRF prevention (blocks internal IPs)
    - Timeout: 10 seconds
    - Max redirects: 3
    - Only allows http/https protocols

    Requires: Any authenticated user

    Returns:
        {
            'url': str (final URL after redirects),
            'title': str (page title),
            'extracted_text': str,
            'fetch_timestamp': str (ISO format),
            'token_estimate': int
        }

    Raises:
        400: If URL is invalid, blocked, or fetch fails
        422: If URL fetched but no content found (SPA/JavaScript page)
        500: If unexpected error occurs
    """
    from app.services.document_parsing_service import NoContentError

    parsing_service = DocumentParsingService()

    try:
        result = parsing_service.fetch_url_content(url)

        # Add token estimate
        result['token_estimate'] = parsing_service.count_tokens_estimate(
            result['extracted_text']
        )

        return result
    except NoContentError as e:
        # No extractable content - return 422 with meta info for fallback options
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "no_content",
                "message": str(e),
                "meta_info": e.meta_info,
                "has_meta": bool(e.meta_info)
            }
        )
    except ValueError as e:
        # Validation errors (invalid URL, blocked IP, etc.)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Fetch errors (timeout, connection failed, etc.)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/fetch-url-meta")
async def fetch_url_meta(
    url: str = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user)
):
    """
    Fetch only meta tags from a URL.

    Use this endpoint as a fallback when the main fetch-url endpoint
    returns no content (e.g., for Single Page Applications).

    Returns:
        {
            'url': str,
            'title': str,
            'extracted_text': str (composed from meta tags),
            'fetch_timestamp': str,
            'token_estimate': int,
            'source': 'meta_tags'
        }
    """
    parsing_service = DocumentParsingService()

    try:
        result = parsing_service.fetch_url_meta_only(url)

        # Add token estimate
        result['token_estimate'] = parsing_service.count_tokens_estimate(
            result['extracted_text']
        )

        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# Queue-Based Analysis Endpoints (Phase 1)
# ============================================================================

class QueueAnalyzeRequest(BaseModel):
    """Schema for queue-based product analysis.

    `web_research` and `source_urls` are scoped-input controls:
    - web_research=False skips Brave search; the agent relies on training
      knowledge + any fetched source pages.
    - source_urls (max 5) are pages fetched server-side and passed to the
      agent as authoritative context.
    """
    product_description: Optional[str] = Field(None, min_length=10)
    source_type: Optional[str] = Field(None, pattern="^(text|document|url)$")
    source_data: Optional[dict] = None
    web_research: bool = True
    source_urls: Optional[List[str]] = None


class JobResponse(BaseModel):
    """Schema for job status response."""
    id: int
    job_uuid: str
    job_type: str
    status: str
    priority: str
    progress_percent: Optional[float]
    progress_message: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    queued_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    product_id: Optional[int]
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


@router.post("/{product_id}/analyze/queue", response_model=JobResponse)
def queue_product_analysis(
    product_id: int,
    request: QueueAnalyzeRequest = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Queue a product for background analysis (async version of /analyze).

    This endpoint queues the analysis job and returns immediately.
    Use GET /jobs/{job_uuid} to check status and retrieve results.

    Requires EDIT permission on the product.

    Returns:
        Job record with job_uuid for status tracking

    Raises:
        403: If user lacks EDIT permission
        404: If product not found
        409: If analysis job already running for this product
    """
    from app.services.permission_service import PermissionService
    from app.queue.product_tasks import analyze_product_task
    from app.services.scoped_input_validator import validate_scoped_inputs, ScopedInputError

    # Validate scoped inputs before any DB work
    web_research = True
    validated_source_urls: list[str] = []
    if request is not None:
        try:
            validated_source_urls = validate_scoped_inputs(request.source_urls)
        except ScopedInputError as err:
            raise HTTPException(status_code=400, detail=err.payload)
        web_research = request.web_research

    # Check permission
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.EDIT
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have EDIT permission for product {product_id}"
        )

    # Get product
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )

    # Check for existing active job
    queue_service = QueueService(db)
    active_jobs = queue_service.get_active_jobs(product_id=product_id)
    analysis_jobs = [j for j in active_jobs if j.job_type == JobType.PRODUCT_ANALYSIS]
    if analysis_jobs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Analysis job already active for product {product_id}. "
                   f"Job ID: {analysis_jobs[0].job_uuid}"
        )

    # Prepare input data
    input_data = {
        'web_research_enabled': web_research,
        'source_urls': validated_source_urls,
    }
    if request:
        if request.product_description:
            input_data['product_description'] = request.product_description
        if request.source_type:
            input_data['source_type'] = request.source_type
        if request.source_data:
            input_data['source_data'] = request.source_data

    # Use product's current data if not provided
    if not input_data.get('product_description'):
        input_data['product_description'] = product.product_description
    if not input_data.get('source_type'):
        input_data['source_type'] = product.product_source_type or 'text'
    input_data['product_name'] = product.product_name

    # Create job
    job = queue_service.create_job(
        job_type=JobType.PRODUCT_ANALYSIS,
        input_data=input_data,
        product_id=product_id,
        user_id=current_user.id,
    )

    # Queue the Celery task
    try:
        celery_result = send_task('analyze_product_task', job.id)
        queue_service.mark_queued(job.id, celery_result.id)
    except Exception as e:
        queue_service.mark_failure(job.id, f"Failed to queue task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue analysis task: {str(e)}"
        )

    return JobResponse(
        id=job.id,
        job_uuid=job.job_uuid,
        job_type=job.job_type.value,
        status=job.status.value,
        priority=job.priority.value,
        progress_percent=job.progress_percent,
        progress_message=job.progress_message,
        error_message=job.error_message,
        created_at=job.created_at,
        queued_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        product_id=job.product_id,
        output_data=job.output_data,
    )


@router.get("/{product_id}/jobs", response_model=List[JobResponse])
def list_product_jobs(
    product_id: int,
    status: Optional[str] = Query(None, description="Filter by status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List jobs for a specific product.

    Requires VIEW permission on the product.

    Args:
        product_id: Product ID
        status: Filter by job status (pending, queued, running, success, failure)
        job_type: Filter by job type (product_analysis, etc.)
        limit: Maximum number of jobs to return (default 20, max 100)

    Returns:
        List of jobs for the product
    """
    from app.services.permission_service import PermissionService

    # Check permission
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.VIEW
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have VIEW permission for product {product_id}"
        )

    # Convert string filters to enums
    status_filter = None
    if status:
        try:
            status_filter = JobStatus(status.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}"
            )

    type_filter = None
    if job_type:
        try:
            type_filter = JobType(job_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid job type: {job_type}"
            )

    queue_service = QueueService(db)
    jobs = queue_service.get_jobs_for_product(
        product_id=product_id,
        status=status_filter,
        job_type=type_filter,
        limit=limit,
    )

    return [
        JobResponse(
            id=j.id,
            job_uuid=j.job_uuid,
            job_type=j.job_type.value,
            status=j.status.value,
            priority=j.priority.value,
            progress_percent=j.progress_percent,
            progress_message=j.progress_message,
            error_message=j.error_message,
            created_at=j.created_at,
            queued_at=j.queued_at,
            started_at=j.started_at,
            completed_at=j.completed_at,
            duration_seconds=j.duration_seconds,
            product_id=j.product_id,
            input_data=j.input_data,
            output_data=j.output_data,
        )
        for j in jobs
    ]


# ============================================================================
# Global Job Endpoints
# ============================================================================

# Create a separate router for job endpoints
jobs_router = APIRouter(
    prefix="/product-intelligence/jobs",
    tags=["Product Intelligence - Jobs"]
)


@jobs_router.get("/{job_uuid}", response_model=JobResponse)
def get_job_status(
    job_uuid: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get status of a specific job by UUID.

    Returns the job status, progress, and results (if complete).
    Poll this endpoint to track job progress.

    Requires VIEW permission on the associated product.

    Returns:
        Job details including status and output_data (if complete)

    Raises:
        403: If user lacks permission
        404: If job not found
    """
    from app.services.permission_service import PermissionService

    queue_service = QueueService(db)
    job = queue_service.get_job_by_uuid(job_uuid)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_uuid} not found"
        )

    # Check permission if job is associated with a product
    if job.product_id:
        permission_service = PermissionService(db)
        if not permission_service.can_access_product(
            user_id=current_user.id,
            product_id=job.product_id,
            required_level=ProductPermissionLevel.VIEW
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this job"
            )

    return JobResponse(
        id=job.id,
        job_uuid=job.job_uuid,
        job_type=job.job_type.value,
        status=job.status.value,
        priority=job.priority.value,
        progress_percent=job.progress_percent,
        progress_message=job.progress_message,
        error_message=job.error_message,
        created_at=job.created_at,
        queued_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        product_id=job.product_id,
        output_data=job.output_data,
    )


@jobs_router.post("/{job_uuid}/cancel", response_model=JobResponse)
def cancel_job(
    job_uuid: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a pending or running job.

    Only jobs that haven't completed can be cancelled.

    Requires EDIT permission on the associated product.

    Returns:
        Updated job with cancelled status

    Raises:
        400: If job cannot be cancelled (already complete)
        403: If user lacks permission
        404: If job not found
    """
    from app.services.permission_service import PermissionService
    from app.services.queue_service import QueueServiceError

    queue_service = QueueService(db)
    job = queue_service.get_job_by_uuid(job_uuid)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_uuid} not found"
        )

    # Check permission if job is associated with a product
    if job.product_id:
        permission_service = PermissionService(db)
        if not permission_service.can_access_product(
            user_id=current_user.id,
            product_id=job.product_id,
            required_level=ProductPermissionLevel.EDIT
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to cancel this job"
            )

    try:
        job = queue_service.cancel_job(job.id)
    except QueueServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return JobResponse(
        id=job.id,
        job_uuid=job.job_uuid,
        job_type=job.job_type.value,
        status=job.status.value,
        priority=job.priority.value,
        progress_percent=job.progress_percent,
        progress_message=job.progress_message,
        error_message=job.error_message,
        created_at=job.created_at,
        queued_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        product_id=job.product_id,
        output_data=job.output_data,
    )


# ============================================================================
# Phase 2: Workflow and Advanced Queue Endpoints
# ============================================================================

class WorkflowStartRequest(BaseModel):
    """Schema for starting a full analysis workflow."""
    skip_analysis: bool = Field(
        default=False,
        description="Skip product analysis (use existing) if already analyzed"
    )
    competitor_ids: Optional[List[int]] = Field(
        default=None,
        description="Specific competitor IDs to analyze (skip discovery if provided)"
    )


class WorkflowStatusResponse(BaseModel):
    """Schema for workflow status response."""
    workflow: dict
    steps: List[dict]
    summary: dict


class CompetitorDiscoveryRequest(BaseModel):
    """Schema for competitor discovery request."""
    max_competitors: int = Field(default=5, ge=1, le=20)


class FeatureExtractionRequest(BaseModel):
    """Schema for feature extraction request."""
    competitor_ids: List[int] = Field(..., min_length=1)
    parallel: bool = Field(default=True)


@router.post("/{product_id}/workflows/full-analysis", response_model=JobResponse)
def start_full_analysis_workflow(
    product_id: int,
    request: WorkflowStartRequest = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Start a full analysis workflow for a product (Phase 2).

    This workflow chains multiple jobs:
    1. Product Analysis (if not skipped)
    2. Competitor Discovery (if no specific competitors provided)
    3. Feature Extraction (parallel for all competitors)

    Use GET /jobs/{job_uuid} to track the parent workflow job.
    Use GET /jobs/{job_uuid}/workflow to see all child job statuses.

    Requires EDIT permission on the product.

    Returns:
        Parent workflow job for tracking

    Raises:
        400: If product not analyzed and skip_analysis=True
        403: If user lacks EDIT permission
        404: If product not found
        409: If workflow already running for this product
    """
    from app.services.permission_service import PermissionService
    from app.queue.workflows import WorkflowService, WorkflowError

    # Check permission
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.EDIT
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have EDIT permission for product {product_id}"
        )

    # Check for existing active workflow
    queue_service = QueueService(db)
    active_jobs = queue_service.get_active_jobs(product_id=product_id)
    workflow_jobs = [j for j in active_jobs if j.job_type == JobType.FULL_WORKFLOW]
    if workflow_jobs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow already active for product {product_id}. "
                   f"Job ID: {workflow_jobs[0].job_uuid}"
        )

    # Parse request
    skip_analysis = False
    competitor_ids = None
    if request:
        skip_analysis = request.skip_analysis
        competitor_ids = request.competitor_ids

    # Start workflow
    workflow_service = WorkflowService(db)
    try:
        workflow_job = workflow_service.start_full_analysis_workflow(
            product_id=product_id,
            user_id=current_user.id,
            skip_analysis=skip_analysis,
            competitor_ids=competitor_ids,
        )
    except WorkflowError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return JobResponse(
        id=workflow_job.id,
        job_uuid=workflow_job.job_uuid,
        job_type=workflow_job.job_type.value,
        status=workflow_job.status.value,
        priority=workflow_job.priority.value,
        progress_percent=workflow_job.progress_percent,
        progress_message=workflow_job.progress_message,
        error_message=workflow_job.error_message,
        created_at=workflow_job.created_at,
        queued_at=workflow_job.queued_at,
        started_at=workflow_job.started_at,
        completed_at=workflow_job.completed_at,
        duration_seconds=workflow_job.duration_seconds,
        product_id=workflow_job.product_id,
        output_data=workflow_job.output_data,
    )


@router.post("/{product_id}/competitors/discover/queue", response_model=JobResponse)
def queue_competitor_discovery(
    product_id: int,
    request: CompetitorDiscoveryRequest = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Queue competitor discovery for a product (Phase 2).

    Discovers competitors using AI-powered web search based on
    the product's analysis data (keywords, category, etc.).

    Requires EDIT permission on the product.
    Product must be analyzed first.

    Returns:
        Job record for tracking

    Raises:
        400: If product not analyzed
        403: If user lacks EDIT permission
        404: If product not found
        409: If discovery job already running
    """
    from app.services.permission_service import PermissionService
    from app.queue.competitor_tasks import discover_competitors_task

    # Check permission
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.EDIT
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have EDIT permission for product {product_id}"
        )

    # Get product
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )

    # Check product is analyzed
    if not product.structured_product_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product {product_id} must be analyzed before competitor discovery"
        )

    # Check for existing active job
    queue_service = QueueService(db)
    active_jobs = queue_service.get_active_jobs(product_id=product_id)
    discovery_jobs = [j for j in active_jobs if j.job_type == JobType.COMPETITOR_DISCOVERY]
    if discovery_jobs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Discovery job already active for product {product_id}. "
                   f"Job ID: {discovery_jobs[0].job_uuid}"
        )

    # Parse request
    max_competitors = 5
    if request:
        max_competitors = request.max_competitors

    # Create job
    job = queue_service.create_job(
        job_type=JobType.COMPETITOR_DISCOVERY,
        input_data={'max_competitors': max_competitors},
        product_id=product_id,
        user_id=current_user.id,
    )

    # Queue the Celery task
    try:
        celery_result = send_task('discover_competitors_task', job.id)
        queue_service.mark_queued(job.id, celery_result.id)
    except Exception as e:
        queue_service.mark_failure(job.id, f"Failed to queue task: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue discovery task: {str(e)}"
        )

    return JobResponse(
        id=job.id,
        job_uuid=job.job_uuid,
        job_type=job.job_type.value,
        status=job.status.value,
        priority=job.priority.value,
        progress_percent=job.progress_percent,
        progress_message=job.progress_message,
        error_message=job.error_message,
        created_at=job.created_at,
        queued_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        product_id=job.product_id,
        output_data=job.output_data,
    )


# DEPRECATED: queue_feature_extraction endpoint has been removed.
# Feature extraction is now handled by the V2 functional audit workflow.
# Use POST /{product_id}/run-competitive-analysis-v2 in competitive_agents.py


@router.get("/{product_id}/competitors", response_model=List[dict])
def list_product_competitors(
    product_id: int,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (active, inactive)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List competitors discovered for a product (Phase 2).

    Returns persistent competitor records with their current feature counts.

    Requires VIEW permission on the product.

    Returns:
        List of competitors with metadata
    """
    from app.services.permission_service import PermissionService
    from app.models.competitor_intelligence import ProductCompetitor, ProductCompetitorFeature

    # Check permission
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.VIEW
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have VIEW permission for product {product_id}"
        )

    # Build query
    query = db.query(ProductCompetitor).filter(ProductCompetitor.product_id == product_id)

    if status_filter:
        query = query.filter(ProductCompetitor.status == status_filter)

    competitors = query.order_by(ProductCompetitor.created_at.desc()).all()

    # Get feature counts
    result = []
    for comp in competitors:
        feature_count = db.query(ProductCompetitorFeature).filter(
            ProductCompetitorFeature.product_competitor_id == comp.id,
            ProductCompetitorFeature.status == 'active'
        ).count()

        result.append({
            'id': comp.id,
            'competitor_name': comp.competitor_name,
            'competitor_url': comp.competitor_url,
            'competitor_description': comp.competitor_description,
            'status': comp.status,
            'monitoring_enabled': comp.monitoring_enabled,
            'last_monitored_at': comp.last_monitored_at.isoformat() if comp.last_monitored_at else None,
            'feature_count': feature_count,
            'created_at': comp.created_at.isoformat() if comp.created_at else None,
            'updated_at': comp.updated_at.isoformat() if comp.updated_at else None,
        })

    return result


@router.get("/{product_id}/competitors/{competitor_id}/features", response_model=List[dict])
def list_competitor_features(
    product_id: int,
    competitor_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List features extracted from a competitor (Phase 2).

    Returns persistent feature records for the specified competitor.

    Requires VIEW permission on the product.

    Returns:
        List of features with metadata
    """
    from app.services.permission_service import PermissionService
    from app.models.competitor_intelligence import ProductCompetitor, ProductCompetitorFeature

    # Check permission
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.VIEW
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have VIEW permission for product {product_id}"
        )

    # Verify competitor belongs to product
    competitor = db.query(ProductCompetitor).filter(
        ProductCompetitor.id == competitor_id,
        ProductCompetitor.product_id == product_id
    ).first()

    if not competitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Competitor {competitor_id} not found for product {product_id}"
        )

    # Get features
    features = db.query(ProductCompetitorFeature).filter(
        ProductCompetitorFeature.product_competitor_id == competitor_id,
        ProductCompetitorFeature.status == 'active'
    ).order_by(
        ProductCompetitorFeature.feature_category,
        ProductCompetitorFeature.feature_name
    ).all()

    return [
        {
            'id': f.id,
            'feature_name': f.feature_name,
            'feature_description': f.feature_description,
            'feature_category': f.feature_category,
            'extraction_confidence': float(f.extraction_confidence) if f.extraction_confidence else None,
            'source_url': f.source_url,
            'first_seen_at': f.first_seen_at.isoformat() if f.first_seen_at else None,
            'last_seen_at': f.last_seen_at.isoformat() if f.last_seen_at else None,
            'status': f.status,
        }
        for f in features
    ]


@jobs_router.get("/{job_uuid}/workflow", response_model=WorkflowStatusResponse)
def get_workflow_status(
    job_uuid: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed workflow status including all child jobs (Phase 2).

    For workflow jobs (FULL_WORKFLOW type), returns the parent job
    and all child jobs with progress summary.

    Requires VIEW permission on the associated product.

    Returns:
        Workflow status with all child job details

    Raises:
        400: If job is not a workflow job
        403: If user lacks permission
        404: If job not found
    """
    from app.services.permission_service import PermissionService
    from app.queue.workflows import WorkflowService, WorkflowError

    queue_service = QueueService(db)
    job = queue_service.get_job_by_uuid(job_uuid)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_uuid} not found"
        )

    # Check this is a workflow job
    if job.job_type != JobType.FULL_WORKFLOW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_uuid} is not a workflow job. Type: {job.job_type.value}"
        )

    # Check permission
    if job.product_id:
        permission_service = PermissionService(db)
        if not permission_service.can_access_product(
            user_id=current_user.id,
            product_id=job.product_id,
            required_level=ProductPermissionLevel.VIEW
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this workflow"
            )

    workflow_service = WorkflowService(db)
    try:
        status_data = workflow_service.get_workflow_status(job.id)
        return WorkflowStatusResponse(**status_data)
    except WorkflowError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# DEPRECATED: backfill-embeddings endpoint has been removed.
# Competitor feature embeddings are now handled by the V2 functional audit workflow.
# Feature embeddings are generated on-the-fly from CompetitorFunctionalReport data.


# ============================================================================
# Pending Counts & Triage Settings (Plan Phase 1, 8)
# ============================================================================

class ProductPendingCountsResponse(BaseModel):
    """Response schema for product pending counts."""
    product_id: int
    ideas_pending: int  # Ideas with status=PENDING
    ideas_needs_review: int  # Ideas with status=NEEDS_REVIEW (flagged by AI)
    competitive_alerts: int  # Pending competitive alerts from PMReviewQueue


class TriageSettingsRequest(BaseModel):
    """Request schema for updating triage automation settings."""
    auto_enabled: bool = Field(..., description="Enable/disable automatic triage responses")
    auto_threshold: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for auto-responses (0.0-1.0)"
    )


class TriageSettingsResponse(BaseModel):
    """Response schema for triage settings."""
    product_id: int
    auto_enabled: bool
    auto_threshold: float


@router.get("/{product_id}/pending-counts", response_model=ProductPendingCountsResponse)
def get_product_pending_counts(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get pending counts for a product.

    Returns counts of items awaiting PO action:
    - ideas_pending: Ideas with status=PENDING
    - ideas_needs_review: Ideas with status=NEEDS_REVIEW
    - competitive_alerts: Pending competitive alerts

    Requires VIEW permission on the product.
    """
    from app.services.permission_service import PermissionService
    from app.models.idea import Idea, IdeaStatus
    from app.models.pm_review import PMReviewQueue, ReviewQueueStatus, ReviewQueueType

    # Check permission
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.VIEW
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have VIEW permission for product {product_id}"
        )

    # Verify product exists
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )

    # Count ideas with PENDING status
    ideas_pending = db.query(Idea).filter(
        Idea.product_id == product_id,
        Idea.status == IdeaStatus.PENDING
    ).count()

    # Count ideas with NEEDS_REVIEW status (were flagged by AI for PO review)
    ideas_needs_review = db.query(Idea).filter(
        Idea.product_id == product_id,
        Idea.status == IdeaStatus.NEEDS_REVIEW
    ).count()

    # Count pending competitive alerts from PM Review Queue
    competitive_alerts = db.query(PMReviewQueue).filter(
        PMReviewQueue.product_id == product_id,
        PMReviewQueue.queue_type == ReviewQueueType.COMPETITIVE_ALERT,
        PMReviewQueue.status == ReviewQueueStatus.PENDING
    ).count()

    return ProductPendingCountsResponse(
        product_id=product_id,
        ideas_pending=ideas_pending,
        ideas_needs_review=ideas_needs_review,
        competitive_alerts=competitive_alerts,
    )


@router.get("/{product_id}/idea-funnel")
def get_idea_funnel(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get idea funnel data for a product.

    Returns counts by triage status, lifecycle status, and triage method
    for building a visual funnel on the dashboard.

    Requires VIEW permission on the product.
    """
    from sqlalchemy import func as sql_func
    from app.services.permission_service import PermissionService
    from app.models.idea import Idea, IdeaStatus
    from app.models.idea_status_history import IdeaStatusHistory
    from app.models.idea_lifecycle_status import IdeaLifecycleStatus

    # Check permission
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.VIEW
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have VIEW permission for product {product_id}"
        )

    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found")

    # Count ideas by triage status
    status_rows = db.query(Idea.status, sql_func.count(Idea.id)).filter(
        Idea.product_id == product_id
    ).group_by(Idea.status).all()

    status_counts = {row[0].value: row[1] for row in status_rows}
    total_submitted = sum(status_counts.values())

    # Count ideas by lifecycle status
    lifecycle_rows = db.query(
        IdeaLifecycleStatus.slug, sql_func.count(Idea.id)
    ).join(
        Idea, Idea.lifecycle_status_id == IdeaLifecycleStatus.id
    ).filter(
        Idea.product_id == product_id
    ).group_by(IdeaLifecycleStatus.slug).all()

    lifecycle_counts = {row[0]: row[1] for row in lifecycle_rows}

    # Count auto-triaged vs manual-triaged
    # Get idea IDs for this product
    product_idea_ids = db.query(Idea.id).filter(Idea.product_id == product_id).subquery()

    auto_triaged = db.query(sql_func.count(IdeaStatusHistory.id)).filter(
        IdeaStatusHistory.idea_id.in_(product_idea_ids),
        IdeaStatusHistory.change_source == 'agent_triage'
    ).scalar() or 0

    manual_triaged = db.query(sql_func.count(IdeaStatusHistory.id)).filter(
        IdeaStatusHistory.idea_id.in_(product_idea_ids),
        IdeaStatusHistory.change_source == 'po_response'
    ).scalar() or 0

    return {
        "product_id": product_id,
        "total_submitted": total_submitted,
        "status_counts": status_counts,
        "lifecycle_counts": lifecycle_counts,
        "auto_triaged_count": auto_triaged,
        "manual_triaged_count": manual_triaged,
    }


@router.get("/{product_id}/triage-settings", response_model=TriageSettingsResponse)
def get_triage_settings(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get triage automation settings for a product.

    Returns the current auto-response configuration.

    Requires VIEW permission on the product.
    """
    from app.services.permission_service import PermissionService

    # Check permission
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.VIEW
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have VIEW permission for product {product_id}"
        )

    # Get product
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )

    return TriageSettingsResponse(
        product_id=product_id,
        auto_enabled=product.idea_triage_auto_enabled,
        auto_threshold=float(product.idea_triage_auto_threshold),
    )


@router.put("/{product_id}/triage-settings", response_model=TriageSettingsResponse)
def update_triage_settings(
    product_id: int,
    request: TriageSettingsRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update triage automation settings for a product.

    Controls automatic idea triage behavior:
    - auto_enabled: When True, ideas with high confidence are automatically responded to
    - auto_threshold: Minimum confidence (0.0-1.0) required for auto-response

    Requires EDIT permission on the product.
    """
    from app.services.permission_service import PermissionService

    # Check permission
    permission_service = PermissionService(db)
    if not permission_service.can_access_product(
        user_id=current_user.id,
        product_id=product_id,
        required_level=ProductPermissionLevel.EDIT
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have EDIT permission for product {product_id}"
        )

    # Get product
    product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product {product_id} not found"
        )

    # Update settings
    product.idea_triage_auto_enabled = request.auto_enabled
    product.idea_triage_auto_threshold = request.auto_threshold

    db.commit()

    return TriageSettingsResponse(
        product_id=product_id,
        auto_enabled=product.idea_triage_auto_enabled,
        auto_threshold=float(product.idea_triage_auto_threshold),
    )
