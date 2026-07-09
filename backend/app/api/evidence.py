"""
Evidence API endpoints for managing the product factbase.

Provides REST CRUD for evidence records — the same data that MCP tools
manage, now accessible from the web UI.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

from app.api.deps import verify_product_access
from app.database import get_db
from app.models.user import User
from app.models.evidence import Evidence, EvidenceType
from app.models.competitor_intelligence import ProductCompetitor, ProductPermissionLevel
from app.services.evidence_service import (
    create_evidence, suggest_competitor, resolve_competitor_by_name
)
from app.utils.security import get_current_active_user

router = APIRouter(
    prefix="/product-intelligence/products",
    tags=["Evidence"]
)


# ============================================================================
# Request/Response Schemas
# ============================================================================

class CreateEvidenceRequest(BaseModel):
    """Request body for creating evidence."""
    evidence_type: str = Field(..., description="One of the EvidenceType enum values")
    title: str = Field(..., max_length=255)
    content: str = Field(..., min_length=1)
    source_url: Optional[str] = Field(None, max_length=500)
    source_description: Optional[str] = Field(None, max_length=255)
    competitor_id: Optional[int] = Field(None, description="Link to existing competitor")
    competitor_name: Optional[str] = Field(None, description="Name for new competitor (created if no match)")
    competitor_url: Optional[str] = Field(None, description="URL for new competitor (used with competitor_name)")
    tags: Optional[List[str]] = None


class SuggestCompetitorRequest(BaseModel):
    """Request body for AI competitor suggestion."""
    title: str
    content: str


class SuggestCompetitorResponse(BaseModel):
    """Response for AI competitor suggestion."""
    suggested_name: Optional[str]
    matched_competitor_id: Optional[int]
    matched_competitor_name: Optional[str]
    is_new: bool


class EvidenceResponse(BaseModel):
    """Response for a single evidence record."""
    id: int
    product_id: int
    evidence_type: str
    title: str
    content: Optional[str] = None
    source_url: Optional[str] = None
    source_description: Optional[str] = None
    competitor_id: Optional[int] = None
    competitor_name: Optional[str] = None
    tags: Optional[List[str]] = None
    jtbd_statement: Optional[str] = None
    created_by: str
    created_at: str
    updated_at: Optional[str] = None


class EvidenceSummaryResponse(BaseModel):
    """Compact response for evidence list items."""
    id: int
    evidence_type: str
    title: str
    source_url: Optional[str] = None
    source_description: Optional[str] = None
    competitor_id: Optional[int] = None
    competitor_name: Optional[str] = None
    tags: Optional[List[str]] = None
    jtbd_statement: Optional[str] = None
    created_at: str


class EvidenceListResponse(BaseModel):
    """Response for evidence list endpoint."""
    product_id: int
    count: int
    evidence: List[EvidenceSummaryResponse]


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/{product_id}/evidence", response_model=EvidenceResponse)
def create_evidence_endpoint(
    product_id: int,
    request: CreateEvidenceRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a new evidence record in the product factbase."""
    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)

    # Validate evidence type
    try:
        ev_type = EvidenceType(request.evidence_type)
    except ValueError:
        valid = [e.value for e in EvidenceType]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid evidence_type '{request.evidence_type}'. Must be one of: {valid}"
        )

    # Resolve competitor
    competitor_id = request.competitor_id

    if not competitor_id and request.competitor_name:
        # Try to match existing competitor
        matched = resolve_competitor_by_name(db, product_id, request.competitor_name)
        if matched:
            competitor_id = matched.id
        else:
            # Create new competitor
            new_competitor = ProductCompetitor(
                product_id=product_id,
                competitor_name=request.competitor_name,
                competitor_url=request.competitor_url or None,
                tracked=True,
                status="active",
            )
            db.add(new_competitor)
            db.flush()
            competitor_id = new_competitor.id

    # Validate competitor_id belongs to this product if provided
    if competitor_id:
        competitor = db.query(ProductCompetitor).filter(
            ProductCompetitor.id == competitor_id,
            ProductCompetitor.product_id == product_id,
        ).first()
        if not competitor:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Competitor {competitor_id} not found for this product"
            )

    evidence = create_evidence(
        db=db,
        product_id=product_id,
        evidence_type=ev_type,
        title=request.title,
        content=request.content,
        source_url=request.source_url,
        source_description=request.source_description,
        competitor_id=competitor_id,
        tags=request.tags,
        created_by="web_ui",
    )
    db.commit()

    result = evidence.to_dict()
    if evidence.competitor_id and evidence.competitor:
        result["competitor_name"] = evidence.competitor.competitor_name
    return result


@router.post("/{product_id}/evidence/suggest-competitor", response_model=SuggestCompetitorResponse)
def suggest_competitor_endpoint(
    product_id: int,
    request: SuggestCompetitorRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Use AI to suggest a competitor association for evidence content."""
    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.VIEW)

    result = suggest_competitor(
        db=db,
        product_id=product_id,
        title=request.title,
        content=request.content,
    )
    return result


@router.get("/{product_id}/evidence", response_model=EvidenceListResponse)
def list_evidence(
    product_id: int,
    competitor_id: Optional[int] = Query(None, description="Filter by competitor"),
    evidence_type: Optional[str] = Query(None, description="Filter by evidence type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List evidence for a product with optional filters."""
    verify_product_access(db, product_id, current_user)

    query = db.query(Evidence).filter(Evidence.product_id == product_id)

    if competitor_id is not None:
        query = query.filter(Evidence.competitor_id == competitor_id)

    if evidence_type:
        try:
            ev_type = EvidenceType(evidence_type)
            query = query.filter(Evidence.evidence_type == ev_type)
        except ValueError:
            pass

    total = query.count()
    results = query.order_by(Evidence.created_at.desc()).offset(offset).limit(limit).all()

    evidence_list = []
    for e in results:
        summary = e.to_summary_dict()
        if e.competitor_id and e.competitor:
            summary["competitor_name"] = e.competitor.competitor_name
        evidence_list.append(summary)

    return {
        "product_id": product_id,
        "count": total,
        "evidence": evidence_list,
    }


@router.get("/{product_id}/evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(
    product_id: int,
    evidence_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get full details for a single evidence record."""
    verify_product_access(db, product_id, current_user)

    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_id,
        Evidence.product_id == product_id,
    ).first()
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence {evidence_id} not found"
        )

    result = evidence.to_dict()
    if evidence.competitor_id and evidence.competitor:
        result["competitor_name"] = evidence.competitor.competitor_name
    return result


@router.delete("/{product_id}/evidence/{evidence_id}")
def delete_evidence(
    product_id: int,
    evidence_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete an evidence record."""
    verify_product_access(db, product_id, current_user, required_level=ProductPermissionLevel.EDIT)

    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_id,
        Evidence.product_id == product_id,
    ).first()
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence {evidence_id} not found"
        )

    db.delete(evidence)
    db.commit()

    return {"message": f"Evidence {evidence_id} deleted", "id": evidence_id}
