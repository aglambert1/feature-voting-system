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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.competitor_intelligence import ProductPermissionLevel
from app.services.product_service import ProductService
from app.services.llm_service import llm_service
from app.utils.security import get_current_active_user


# Create router with /competitor-intelligence/products prefix
router = APIRouter(
    prefix="/competitor-intelligence/products",
    tags=["Competitor Intelligence - Products"]
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


class ProductAnalyzeRequest(BaseModel):
    """Schema for analyzing a product (Stage 1)."""
    product_description: str = Field(..., min_length=10)
    source_type: str = Field(..., pattern="^(text|document|url)$")
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

    class Config:
        from_attributes = True


# ============================================================================
# Product CRUD Endpoints
# ============================================================================

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    request: ProductCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new product WITHOUT automatic analysis (Stage 0).

    Products are created as team resources. The creator gets implicit ADMIN access.
    Other users can be granted VIEW/EDIT/ADMIN permissions separately.

    After creation, use POST /products/{id}/analyze to analyze the product.

    Returns:
        Created product with analysis_version=0 (not yet analyzed)

    Raises:
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


@router.post("/{product_id}/analyze", response_model=dict)
def analyze_product(
    product_id: int,
    request: ProductAnalyzeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Analyze a product with AI (Stage 1 - Independent Operation).

    This can be called multiple times to re-analyze a product as it evolves.
    Each analysis is versioned and stored in analysis history.

    Requires EDIT permission on the product.

    Returns:
        Analyzed product structure including:
        - product_name (AI-refined)
        - product_category
        - core_features
        - target_users
        - value_propositions
        - competitor_search_keywords

    Raises:
        403: If user lacks EDIT permission
        404: If product not found
    """
    service = ProductService(db)

    try:
        analyzed_structure = service.analyze_product(
            product_id=product_id,
            user_id=current_user.id,
            product_description=request.product_description,
            source_type=request.source_type,
            source_data=request.source_data,
            llm_service=llm_service
        )
        return {
            "product_id": product_id,
            "analysis_version": analyzed_structure.get("version", "latest"),
            "analyzed_structure": analyzed_structure
        }
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
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

    Returns products based on:
    - User's default_product_access mode (SINGLE_USER vs TEAM_WIDE)
    - Explicit product permission grants
    - System role (ADMIN sees all)

    Args:
        permission_level: Filter by minimum permission level (view, edit, admin)

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
    Get a product by ID.

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
                "created_at": h.created_at.isoformat() + 'Z' if h.created_at else None
            }
            for h in history
        ]
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


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


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a product (hard delete).

    This will cascade delete all related data:
    - Analysis sessions
    - Competitors
    - Features
    - Generated ideas
    - Permissions

    Requires ADMIN permission on the product.

    Raises:
        403: If user lacks ADMIN permission
        404: If product not found
    """
    service = ProductService(db)

    try:
        success = service.delete_product(product_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found"
            )
        return None
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
