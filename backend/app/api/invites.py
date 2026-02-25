"""
Invite code API endpoints.

Endpoints for managing product invite codes and redeeming them:
- POST /products/{product_id}/invite-codes — Create invite code (PO)
- GET /products/{product_id}/invite-codes — List invite codes (PO)
- DELETE /products/{product_id}/invite-codes/{code_id} — Deactivate code (PO)
- GET /products/{product_id}/members — List product members (PO)
- POST /invites/redeem — Redeem an invite code (authenticated user)
- GET /invites/{code}/info — Get invite code info (public)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.competitor_intelligence import (
    CIProduct, ProductPermission, ProductPermissionLevel
)
from app.models.product_invite import ProductInviteCode
from app.services.permission_service import PermissionService
from app.utils.security import get_current_active_user


router = APIRouter(tags=["Invites"])


# ============================================================================
# Schemas
# ============================================================================

class CreateInviteCodeRequest(BaseModel):
    max_uses: Optional[int] = Field(None, ge=1, description="Max redemptions (null = unlimited)")
    expires_at: Optional[datetime] = Field(None, description="Expiration datetime (null = never)")


class InviteCodeResponse(BaseModel):
    id: int
    product_id: int
    code: str
    invite_url: str
    max_uses: Optional[int]
    current_uses: int
    permission_level: str
    expires_at: Optional[datetime]
    is_active: bool
    created_at: datetime


class RedeemInviteRequest(BaseModel):
    code: str = Field(..., min_length=1, description="Invite code to redeem")


class RedeemInviteResponse(BaseModel):
    product_id: int
    product_name: str
    message: str


class InviteInfoResponse(BaseModel):
    valid: bool
    product_name: Optional[str] = None
    message: str


class ProductMemberResponse(BaseModel):
    user_id: int
    username: str
    email: str
    permission_level: str
    granted_at: datetime


# ============================================================================
# Helper
# ============================================================================

def _build_invite_url(code: str) -> str:
    """Build the full invite URL for a code."""
    # Frontend will handle /join/:code route
    return f"/join/{code}"


def _check_po_access(db: Session, user: User, product_id: int) -> CIProduct:
    """Verify product exists and user has EDIT permission."""
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
        required_level=ProductPermissionLevel.EDIT
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage this product"
        )

    return product


# ============================================================================
# PO Invite Code Management
# ============================================================================

@router.post(
    "/products/{product_id}/invite-codes",
    response_model=InviteCodeResponse,
    status_code=status.HTTP_201_CREATED
)
def create_invite_code(
    product_id: int,
    request: CreateInviteCodeRequest = CreateInviteCodeRequest(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new invite code for a product."""
    _check_po_access(db, current_user, product_id)

    invite = ProductInviteCode(
        product_id=product_id,
        code=ProductInviteCode.generate_code(),
        created_by_user_id=current_user.id,
        max_uses=request.max_uses,
        permission_level=ProductPermissionLevel.VIEW,
        expires_at=request.expires_at,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return InviteCodeResponse(
        id=invite.id,
        product_id=invite.product_id,
        code=invite.code,
        invite_url=_build_invite_url(invite.code),
        max_uses=invite.max_uses,
        current_uses=invite.current_uses,
        permission_level=invite.permission_level.value,
        expires_at=invite.expires_at,
        is_active=invite.is_active,
        created_at=invite.created_at,
    )


@router.get("/products/{product_id}/invite-codes", response_model=List[InviteCodeResponse])
def list_invite_codes(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all invite codes for a product."""
    _check_po_access(db, current_user, product_id)

    codes = db.query(ProductInviteCode).filter(
        ProductInviteCode.product_id == product_id
    ).order_by(ProductInviteCode.created_at.desc()).all()

    return [
        InviteCodeResponse(
            id=c.id,
            product_id=c.product_id,
            code=c.code,
            invite_url=_build_invite_url(c.code),
            max_uses=c.max_uses,
            current_uses=c.current_uses,
            permission_level=c.permission_level.value,
            expires_at=c.expires_at,
            is_active=c.is_active,
            created_at=c.created_at,
        )
        for c in codes
    ]


@router.delete(
    "/products/{product_id}/invite-codes/{code_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def deactivate_invite_code(
    product_id: int,
    code_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Deactivate an invite code (soft delete)."""
    _check_po_access(db, current_user, product_id)

    invite = db.query(ProductInviteCode).filter(
        ProductInviteCode.id == code_id,
        ProductInviteCode.product_id == product_id
    ).first()

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite code not found"
        )

    invite.is_active = False
    db.commit()


# ============================================================================
# Product Members
# ============================================================================

@router.get("/products/{product_id}/members", response_model=List[ProductMemberResponse])
def list_product_members(
    product_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List users with access to a product."""
    _check_po_access(db, current_user, product_id)

    permissions = db.query(ProductPermission, User).join(
        User, ProductPermission.user_id == User.id
    ).filter(
        ProductPermission.product_id == product_id
    ).all()

    return [
        ProductMemberResponse(
            user_id=user.id,
            username=user.username,
            email=user.email,
            permission_level=perm.permission_level.value,
            granted_at=perm.granted_at,
        )
        for perm, user in permissions
    ]


# ============================================================================
# Invite Code Redemption
# ============================================================================

@router.post("/invites/redeem", response_model=RedeemInviteResponse)
def redeem_invite_code(
    request: RedeemInviteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Redeem an invite code to gain product access."""
    invite = db.query(ProductInviteCode).filter(
        ProductInviteCode.code == request.code
    ).first()

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite code"
        )

    if not invite.is_valid():
        if not invite.is_active:
            detail = "This invite code has been deactivated"
        elif invite.is_expired():
            detail = "This invite code has expired"
        elif invite.is_at_max_uses():
            detail = "This invite code has reached its usage limit"
        else:
            detail = "This invite code is no longer valid"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    # Check if user already has access to this product
    existing = db.query(ProductPermission).filter(
        ProductPermission.product_id == invite.product_id,
        ProductPermission.user_id == current_user.id
    ).first()

    product = db.query(CIProduct).filter(CIProduct.id == invite.product_id).first()
    product_name = product.product_name if product else "Unknown"

    if existing:
        return RedeemInviteResponse(
            product_id=invite.product_id,
            product_name=product_name,
            message=f"You already have access to {product_name}"
        )

    # Grant permission directly — the invite code itself is the authorization,
    # so we bypass grant_permission()'s granter-level check.
    perm = ProductPermission(
        product_id=invite.product_id,
        user_id=current_user.id,
        permission_level=invite.permission_level,
        granted_by_user_id=invite.created_by_user_id,
    )
    db.add(perm)

    # Increment usage
    invite.current_uses += 1
    db.commit()

    return RedeemInviteResponse(
        product_id=invite.product_id,
        product_name=product_name,
        message=f"You now have access to {product_name}"
    )


@router.get("/invites/{code}/info", response_model=InviteInfoResponse)
def get_invite_info(
    code: str,
    db: Session = Depends(get_db)
):
    """
    Get info about an invite code. Public endpoint (no auth required).
    Used by the registration page to show product name.
    """
    invite = db.query(ProductInviteCode).filter(
        ProductInviteCode.code == code
    ).first()

    if not invite or not invite.is_valid():
        return InviteInfoResponse(
            valid=False,
            message="This invite code is invalid or has expired"
        )

    product = db.query(CIProduct).filter(CIProduct.id == invite.product_id).first()
    product_name = product.product_name if product else "Unknown"

    return InviteInfoResponse(
        valid=True,
        product_name=product_name,
        message=f"You've been invited to vote on {product_name}"
    )
