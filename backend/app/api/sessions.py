"""
Session API endpoints for competitor intelligence analysis.

This module provides REST API endpoints for creating and managing
analysis sessions. Sessions are lightweight workflow containers that
track progression through CI stages (competitor discovery, feature analysis).

Products must be created and analyzed BEFORE creating a session.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.schemas.competitor_intelligence import SessionCreate
from app.services.session_service import SessionService
from app.services.competitor_intelligence_service import CompetitorIntelligenceService
from app.services.llm_service import llm_service
from app.utils.security import get_current_active_user
from app.database import get_db
from app.models.user import User


router = APIRouter(
    prefix="/competitor-intelligence/sessions",
    tags=["Competitor Intelligence - Sessions"]
)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_session(
    session_data: SessionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a new analysis session for an existing, analyzed product.

    Sessions are lightweight workflow containers. They track progression
    through competitive intelligence stages but do NOT create or analyze products.

    **Prerequisites:**
    1. Product must exist (create with POST /products)
    2. Product must be analyzed (analyze with POST /products/{id}/analyze)

    Args:
        session_data: Must include product_id of existing analyzed product
        current_user: Authenticated user
        db: Database session

    Returns:
        Session details with analyzed product structure

    Raises:
        400: If product_id missing, product not found, or not analyzed
        403: If user lacks VIEW permission on product
    """
    service = SessionService(db)

    # Validate product_id is provided
    if not session_data.product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "product_id is required. "
                "Create and analyze a product first:\n"
                "1. POST /competitor-intelligence/products\n"
                "2. POST /competitor-intelligence/products/{id}/analyze"
            )
        )

    try:
        session = service.create_session(
            user_id=current_user.id,
            product_id=session_data.product_id,
            session_name=session_data.session_name,
            enable_comparison=session_data.enable_comparison
        )

        return {
            "id": session.id,
            "product_id": session.product_id,
            "session_number": session.session_number,
            "session_name": session.session_name,
            "analysis_type": session.analysis_type,
            "status": session.status,
            "analyzed_product": session.analyzed_product_structure,
            "has_previous_analysis": session.analysis_type == "differential",
            "created_at": session.created_at.isoformat() if session.created_at else None
        }
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


@router.get("/{session_id}")
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get session details.

    Requires VIEW permission on the associated product.

    Args:
        session_id: Session ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Session details with analyzed product structure

    Raises:
        403: If user lacks VIEW permission
        404: If session not found
    """
    service = SessionService(db)
    session = service.get_session(session_id, current_user.id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or you don't have permission to view it"
        )

    return {
        "id": session.id,
        "product_id": session.product_id,
        "session_number": session.session_number,
        "session_name": session.session_name,
        "analysis_type": session.analysis_type,
        "status": session.status,
        "analyzed_product": session.analyzed_product_structure,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None
    }


@router.get("/products/{product_id}/sessions")
def list_product_sessions(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List all sessions for a product.

    Requires VIEW permission on the product.

    Args:
        product_id: Product ID
        current_user: Authenticated user
        db: Database session

    Returns:
        List of sessions ordered by session number (newest first)

    Raises:
        403: If user lacks VIEW permission
        404: If product not found
    """
    service = SessionService(db)

    try:
        sessions = service.list_product_sessions(product_id, current_user.id)
        return [
            {
                "id": s.id,
                "session_number": s.session_number,
                "session_name": s.session_name,
                "analysis_type": s.analysis_type,
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None
            }
            for s in sessions
        ]
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.patch("/{session_id}/status")
def update_session_status(
    session_id: int,
    status_value: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update session status.

    Requires EDIT permission on the associated product.

    Args:
        session_id: Session ID
        status_value: New status (active, completed, archived)
        current_user: Authenticated user
        db: Database session

    Returns:
        Success confirmation

    Raises:
        403: If user lacks EDIT permission
        404: If session not found
    """
    service = SessionService(db)

    try:
        success = service.update_session_status(
            session_id=session_id,
            user_id=current_user.id,
            status=status_value
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        return {"status": "updated"}
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a session.

    Requires ADMIN permission on the associated product.

    Args:
        session_id: Session ID
        current_user: Authenticated user
        db: Database session

    Raises:
        403: If user lacks ADMIN permission
        404: If session not found
    """
    service = SessionService(db)

    try:
        success = service.delete_session(session_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        return None
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


# ============================================================================
# Competitor Discovery Endpoints (Stage 2)
# ============================================================================

class ConfirmCompetitorsRequest(BaseModel):
    """Schema for confirming competitor selection"""
    selected_ids: List[int]
    custom_competitors: Optional[List[dict]] = None


@router.post("/{session_id}/discover-competitors")
async def discover_competitors(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Discover competitors for a session using AI research (Stage 2).

    If session has comparison enabled, performs differential analysis
    to identify NEW/CONTINUING/DISAPPEARED competitors.

    Args:
        session_id: Session UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict containing:
        - competitors: List of discovered competitors with details
        - change_summary: Differential analysis (if applicable)
        - research_summary: Overview of competitive landscape
        - has_comparison: Whether comparison was performed

    Raises:
        404: If session not found
    """
    service = CompetitorIntelligenceService(db)

    try:
        result = await service.discover_competitors(
            session_id=session_id,
            llm_service=llm_service
        )

        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/{session_id}/competitors")
async def get_session_competitors(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all competitors for a session.

    Args:
        session_id: Session UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        List of competitors with selection status
    """
    service = CompetitorIntelligenceService(db)

    competitors = await service.get_session_competitors(session_id)

    return {
        'competitors': competitors
    }


@router.post("/{session_id}/confirm-competitors")
async def confirm_competitors(
    session_id: int,
    data: ConfirmCompetitorsRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Confirm which competitors to analyze (Stage 2 → Stage 3).

    User selects from discovered competitors and/or adds custom ones.
    Marks selected competitors for feature extraction.

    Args:
        session_id: Session UUID
        data: Selected competitor IDs and optional custom competitors
        current_user: Authenticated user
        db: Database session

    Returns:
        Confirmation with selected count
    """
    service = CompetitorIntelligenceService(db)

    result = await service.confirm_competitors(
        session_id=session_id,
        selected_ids=data.selected_ids,
        custom_competitors=data.custom_competitors
    )

    return result
