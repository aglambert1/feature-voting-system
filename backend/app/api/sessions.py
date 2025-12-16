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
from uuid import UUID
from pydantic import BaseModel

from app.schemas.competitor_intelligence import SessionCreate
from app.services.session_service import SessionService
from app.services.competitor_intelligence_service import CompetitorIntelligenceService
from app.services.feature_extraction_service import FeatureExtractionService
from app.services.idea_generation_service import IdeaGenerationService
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
            enable_comparison=session_data.enable_comparison,
            previous_session_id=session_data.previous_session_id
        )

        return {
            "id": session.id,
            "product_id": session.product_id,
            "session_number": session.session_number,
            "session_name": session.session_name,
            "analysis_type": session.analysis_type,
            "comparison_to_session_id": session.comparison_to_session_id,
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
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "competitors_count": len([c for c in s.session_competitors if c.selected_by_user])
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


@router.post("/{session_id}/copy-competitors/{from_session_id}")
async def copy_competitors_from_session(
    session_id: int,
    from_session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Copy competitors from another session to this session.

    Useful for reusing competitor discoveries without re-running AI.
    Automatically deduplicates - won't create duplicates if competitors
    already exist in the destination session.

    Args:
        session_id: Destination session ID (current session)
        from_session_id: Source session ID (previous session to copy from)
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict with copied_count, skipped_count, and total_source
    """
    service = CompetitorIntelligenceService(db)

    try:
        result = await service.copy_competitors_from_session(
            from_session_id=from_session_id,
            to_session_id=session_id
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


@router.get("/{session_id}/competitors/feature-availability")
async def check_competitor_feature_availability(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Check which selected competitors have extractable features from previous sessions.

    For each selected competitor, checks if they have a ProductCompetitor record
    with extracted features from ANY previous session (not just the comparison session).

    Args:
        session_id: Current session ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict with competitor feature availability:
        {
            "competitors_with_features": [
                {
                    "session_competitor_id": int,
                    "product_competitor_id": int,
                    "competitor_name": str,
                    "features_count": int,
                    "last_extraction_session_id": int
                },
                ...
            ],
            "total_selected": int,
            "with_features": int
        }
    """
    from app.models.competitor_intelligence import SessionCompetitor, ProductCompetitorFeature

    # Get selected competitors for this session
    competitors = db.query(SessionCompetitor).filter(
        SessionCompetitor.session_id == session_id,
        SessionCompetitor.selected_by_user == True,
        SessionCompetitor.product_competitor_id.isnot(None)
    ).all()

    competitors_with_features = []

    for comp in competitors:
        # Check if this ProductCompetitor has extracted features
        features_count = db.query(ProductCompetitorFeature).filter(
            ProductCompetitorFeature.product_competitor_id == comp.product_competitor_id
        ).count()

        if features_count > 0:
            # Get the most recent session where features were extracted
            # (We can infer this from the ProductCompetitor's last_seen_session_id)
            competitors_with_features.append({
                "session_competitor_id": comp.id,
                "product_competitor_id": comp.product_competitor_id,
                "competitor_name": comp.competitor_name,
                "features_count": features_count,
                "last_extraction_session_id": comp.product_competitor.last_seen_session_id
            })

    return {
        "competitors_with_features": competitors_with_features,
        "total_selected": len(competitors),
        "with_features": len(competitors_with_features)
    }


# ============================================================================
# Feature Extraction Endpoints (Stage 3)
# ============================================================================

class SelectFeaturesRequest(BaseModel):
    """Schema for selecting features"""
    feature_ids: List[int]


@router.post("/{session_id}/extract-features")
async def extract_features(
    session_id: int,
    reuse_existing: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Extract features from selected competitors (Stage 3).

    Analyzes each selected competitor's website/data to extract features.
    If session has comparison enabled, detects changes from previous analysis.

    Args:
        session_id: Session ID
        reuse_existing: If True, reuse existing ProductCompetitorFeature without AI extraction (default: False)
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict containing:
        - status: Extraction status
        - total_competitors: Number of competitors being analyzed
        - comparison_mode: Whether change detection is enabled

    Raises:
        404: If session not found
        400: If no competitors selected
    """
    service = FeatureExtractionService(db)

    try:
        result = await service.extract_features_for_session(
            session_id=session_id,
            llm_service=llm_service,
            reuse_existing=reuse_existing
        )

        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{session_id}/features")
async def get_session_features(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all extracted features for a session.

    Returns features grouped by competitor with change tracking data.

    Args:
        session_id: Session ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict containing:
        - features_by_competitor: List of competitors with their features
        - change_stats: Summary of changes (if comparison enabled)
    """
    service = FeatureExtractionService(db)

    result = await service.get_session_features(session_id)

    return result


@router.get("/features/{feature_id}/details")
async def get_feature_details(
    feature_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get expanded details for a specific feature.

    Uses AI to provide detailed explanation of the feature including
    technical details, use cases, benefits, and limitations.

    Args:
        feature_id: Feature ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict containing:
        - feature_id: Feature ID
        - expanded_description: Detailed description
        - technical_details: Technical information
        - use_cases: List of use cases
        - benefits: List of benefits
        - limitations: List of limitations (if any)
        - cached: Whether details were previously retrieved

    Raises:
        404: If feature not found
    """
    service = FeatureExtractionService(db)

    try:
        result = await service.expand_feature_details(
            feature_id=feature_id,
            llm_service=llm_service
        )

        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/{session_id}/select-features")
async def select_features(
    session_id: int,
    data: SelectFeaturesRequest = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Select features for idea generation (Stage 3 → Stage 4).

    User chooses which extracted features to use for generating ideas.

    Args:
        session_id: Session ID
        data: List of feature IDs to select
        current_user: Authenticated user
        db: Database session

    Returns:
        Confirmation with selected count
    """
    service = FeatureExtractionService(db)

    result = await service.select_features(
        session_id=session_id,
        feature_ids=data.feature_ids
    )

    return result


# ============================================================================
# Idea Generation Endpoints (Stage 4)
# ============================================================================

class EditIdeaRequest(BaseModel):
    """Schema for editing a generated idea"""
    what: Optional[str] = None
    why: Optional[str] = None
    use_case: Optional[str] = None


class ApproveIdeasRequest(BaseModel):
    """Schema for approving/rejecting generated ideas"""
    idea_ids: List[int]
    approved: bool = True


@router.post("/{session_id}/generate-ideas")
async def generate_ideas_for_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate ideas from selected competitor features (Stage 3 → Stage 4).

    This endpoint:
    1. Gets all selected features from the session
    2. Runs the IdeaStructuringAgent to adapt features to the product
    3. Stores generated ideas in competitor_generated_ideas table
    4. Returns all generated ideas for review

    Prerequisites:
    - Session must exist
    - At least one feature must be selected (selected_by_user = True)

    Args:
        session_id: Session ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Generated ideas with adaptation notes

    Raises:
        404: Session not found
        400: No features selected
        500: Idea generation failed
    """
    service = IdeaGenerationService(db)

    try:
        result = service.generate_ideas_for_session(
            session_id=session_id,
            llm_service=llm_service
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Idea generation failed: {str(e)}"
        )


@router.get("/{session_id}/generated-ideas")
def get_generated_ideas(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all generated ideas for a session.

    Returns all CompetitorGeneratedIdea records for the session,
    including their approval status and link to source features.

    Args:
        session_id: Session ID
        current_user: Authenticated user
        db: Database session

    Returns:
        List of generated ideas with metadata
    """
    service = IdeaGenerationService(db)
    return service.get_generated_ideas(session_id)


@router.put("/generated-ideas/{idea_id}")
def edit_generated_idea(
    idea_id: int,
    edit_data: EditIdeaRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Edit a generated idea.

    Allows users to refine AI-generated ideas before approval.
    Marks the idea as user_edited and tracks the edit timestamp.

    Args:
        idea_id: Generated idea ID
        edit_data: Fields to update (what, why, use_case)
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated idea data

    Raises:
        404: Idea not found
    """
    service = IdeaGenerationService(db)

    try:
        result = service.edit_generated_idea(
            idea_id=idea_id,
            what=edit_data.what,
            why=edit_data.why,
            use_case=edit_data.use_case
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/generated-ideas/approve")
def approve_generated_ideas(
    approve_data: ApproveIdeasRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Approve or reject generated ideas.

    Sets user_approved flag for specified ideas.
    Only approved ideas will be submitted to the voting system.

    Args:
        approve_data: Idea IDs and approval status
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated counts
    """
    service = IdeaGenerationService(db)
    return service.approve_generated_ideas(
        idea_ids=approve_data.idea_ids,
        approved=approve_data.approved
    )


# ============================================================================
# Idea Finalization Endpoints (Stage 5)
# ============================================================================

@router.post("/{session_id}/finalize")
def finalize_session_ideas(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Submit approved ideas to the main voting system (Stage 4 → Stage 5 → Complete).

    This is the final step in the competitor intelligence workflow.
    Creates Idea records for all approved CompetitorGeneratedIdea records.

    What happens:
    1. Gets all approved, unsubmitted ideas from the session
    2. Creates Idea records with source_type='competitor_automated'
    3. Links CompetitorGeneratedIdea.final_idea_id to Idea.id
    4. Marks ideas as submitted_to_ideas=True
    5. Sets session stage to 'completed'

    Args:
        session_id: Session ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Submission results with idea IDs

    Raises:
        404: Session not found
        400: No approved ideas to submit
    """
    service = IdeaGenerationService(db)

    try:
        result = service.finalize_ideas(session_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
