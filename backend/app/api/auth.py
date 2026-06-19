"""
Authentication routes.

This file contains all endpoints related to user authentication:
- POST /auth/register - Create a new user account
- POST /auth/login - Log in and get an access token
- GET /auth/me - Get current user information
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User, UserRole
from app.models.product_invite import ProductInviteCode
from app.models.competitor_intelligence import ProductPermission, ProductPermissionLevel, CIProduct
from app.services.permission_service import PermissionService
from app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    UserRoleUpdate,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordChange,
    MessageResponse,
    PasswordResetResponse,
    DevOTPResponse
)
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_active_user,
    get_current_admin_user,
    get_current_user
)


# Create a router for authentication endpoints
# All routes in this file will be prefixed with /auth
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    """
    Register a new user account.

    Two modes:
    1. Self-registration: requires a valid invite_code. User gets VOTER role
       and product access from the invite code.
    2. Admin-created: admin can specify role and product_ids. No invite code needed.

    Returns:
        The newly created user information

    Raises:
        400 Bad Request: If email/username exists or invite code is invalid
    """
    # Check if an admin is making this request (optional auth)
    is_admin_creating = False
    admin_user = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from jose import jwt
            from app.config import settings
            token = auth_header.split(" ", 1)[1]
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            user_id = payload.get("user_id")
            if user_id:
                admin_user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
                if admin_user and admin_user.role == UserRole.ADMIN:
                    is_admin_creating = True
        except Exception:
            pass  # Not admin — continue with self-registration flow

    # Validate invite code for self-registration
    invite = None
    if not is_admin_creating:
        if not user_data.invite_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An invite code is required to register. Contact a Product Owner for an invite link."
            )

        invite = db.query(ProductInviteCode).filter(
            ProductInviteCode.code == user_data.invite_code
        ).first()

        if not invite or not invite.is_valid():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired invite code"
            )

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Create new user with hashed password
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role if user_data.role else None  # Defaults to VOTER
    )

    db.add(new_user)
    db.flush()  # Assigns new_user.id without committing

    # Grant product access
    if invite:
        # Self-registration: grant access from invite code
        # Create permission directly — the invite code itself is the authorization,
        # so we bypass grant_permission()'s granter-level check.
        perm = ProductPermission(
            product_id=invite.product_id,
            user_id=new_user.id,
            permission_level=invite.permission_level,
            granted_by_user_id=invite.created_by_user_id,
        )
        db.add(perm)
        invite.current_uses += 1
    elif is_admin_creating and user_data.product_ids:
        # Admin-created: grant access to specified products
        perm_level = (
            ProductPermissionLevel.EDIT
            if user_data.role == UserRole.PRODUCT_OWNER
            else ProductPermissionLevel.VIEW
        )
        for product_id in user_data.product_ids:
            product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
            if product:
                perm = ProductPermission(
                    product_id=product_id,
                    user_id=new_user.id,
                    permission_level=perm_level,
                    granted_by_user_id=admin_user.id,
                )
                db.add(perm)

    # Commit user + permission(s) together as one transaction
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Log in and get an access token.

    This endpoint accepts standard OAuth2 password flow:
    - username: Can be either username or email
    - password: User's password

    Steps:
    1. Find user by username or email
    2. Verify password
    3. Create JWT token
    4. Return token

    Args:
        form_data: OAuth2 form with username and password
        db: Database session

    Returns:
        Access token and token type

    Raises:
        401 Unauthorized: If credentials are incorrect
    """
    # Try to find user by username first, then by email
    user = db.query(User).filter(User.username == form_data.username).first()

    if not user:
        # Try finding by email
        user = db.query(User).filter(User.email == form_data.username).first()

    # If user doesn't exist or password is wrong
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    # Create access token
    # "sub" (subject) is a standard JWT claim for the user identifier
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get information about the currently logged-in user.

    This is a protected route - you must include a valid token in the header:
    Authorization: Bearer <your_token_here>

    Args:
        current_user: Automatically extracted from the JWT token

    Returns:
        Current user's information
    """
    return current_user


@router.post("/me/mark-welcomed", response_model=UserResponse)
async def mark_welcomed(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Flip the current user's has_seen_welcome flag to True.

    Called by the frontend WelcomePage when the user clicks the explicit
    "Got it" CTA. Bouncing out of the welcome page without clicking the CTA
    leaves the flag false, so the user re-sees the page on next login.

    Idempotent - flipping an already-true flag is a no-op.
    """
    if not current_user.has_seen_welcome:
        current_user.has_seen_welcome = True
        db.commit()
        db.refresh(current_user)
    return current_user

@router.get("/users", response_model=list[UserResponse])
async def get_all_users(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get all users and their roles.

    This is a protected route - requires admin authentication.
    Only admins can view the list of all users.

    Args:
        current_user: Automatically extracted from the JWT token (must be admin)
        db: Database session

    Returns:
        List of all users with their information and roles
    """
    users = db.query(User).all()
    return users


@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update a user's role.

    This is an admin-only endpoint for changing user roles.
    Admins can promote users to admin, voter, or viewer roles.

    Args:
        user_id: The ID of the user to update
        role_update: The new role to assign
        current_user: The admin performing the action
        db: Database session

    Returns:
        The updated user information

    Raises:
        404 Not Found: If user doesn't exist
        400 Bad Request: If trying to change your own role
    """
    # Find the user to update
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent admin from changing their own role (security measure)
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role"
        )

    # Update the role
    user.role = role_update.role
    db.commit()
    db.refresh(user)

    return user


@router.patch("/users/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Deactivate a user account.

    This is an admin-only endpoint for deactivating users.
    Deactivated users cannot log in but their data is preserved.
    This is safer than deleting users.

    Args:
        user_id: The ID of the user to deactivate
        current_user: The admin performing the action
        db: Database session

    Returns:
        The updated user information

    Raises:
        404 Not Found: If user doesn't exist
        400 Bad Request: If trying to deactivate yourself
    """
    # Find the user to deactivate
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent admin from deactivating themselves
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account"
        )

    # Deactivate the user
    user.is_active = False
    db.commit()
    db.refresh(user)

    return user


@router.patch("/users/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Activate a user account.

    This is an admin-only endpoint for reactivating deactivated users.

    Args:
        user_id: The ID of the user to activate
        current_user: The admin performing the action
        db: Database session

    Returns:
        The updated user information

    Raises:
        404 Not Found: If user doesn't exist
    """
    # Find the user to activate
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Activate the user
    user.is_active = True
    db.commit()
    db.refresh(user)

    return user


# =============================================================================
# PASSWORD MANAGEMENT ENDPOINTS
# =============================================================================


@router.post("/password/reset-request", response_model=PasswordResetResponse)
@limiter.limit("3/minute")
async def request_password_reset(
    request: Request,
    reset_request: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Request a password reset (sends OTP to email).

    This is a public endpoint - no authentication required.
    User provides their email and receives a 6-digit OTP code.

    Steps:
    1. Find user by email
    2. Generate 6-digit OTP
    3. Store OTP in database with expiration (15 minutes)
    4. Send OTP to user's email
    5. Return success message

    Args:
        request: Password reset request with email
        db: Database session

    Returns:
        Success message

    Raises:
        404 Not Found: If email doesn't exist (for security, we may want to return success anyway)
    """
    from app.models.password_reset import PasswordResetToken
    from app.utils.otp import generate_otp, get_otp_expiration
    from app.utils.email import email_service
    from app.config import settings
    from datetime import datetime, timezone

    # Find user by email
    user = db.query(User).filter(User.email == reset_request.email).first()

    # Security consideration: Don't reveal if email exists or not
    # Always return success, but only send email if user exists
    if not user:
        # Return success even if user doesn't exist (prevents email enumeration)
        return PasswordResetResponse(
            message="If this email is registered, you will receive a password reset code.",
            detail="Check your email for the OTP code."
        )

    # Invalidate any existing unused tokens for this user
    existing_tokens = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.is_used == False
    ).all()

    for token in existing_tokens:
        token.is_used = True

    # Generate new OTP
    otp = generate_otp()
    expiration = get_otp_expiration(minutes=15)

    # Create password reset token
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=otp,
        expires_at=expiration
    )

    db.add(reset_token)
    db.commit()

    # Send OTP via email
    await email_service.send_password_reset_otp(
        to_email=user.email,
        otp=otp,
        username=user.username
    )

    # In development mode, return the OTP in the response for easy testing
    response = PasswordResetResponse(
        message="If this email is registered, you will receive a password reset code.",
        detail="Check your email for the OTP code. It expires in 15 minutes."
    )

    if settings.debug and settings.dev_return_otp:
        response.dev_otp = otp
        response.detail = f"[DEV MODE] OTP: {otp} | Expires in 15 minutes. Also logged to console."

    return response


@router.post("/password/reset-confirm", response_model=MessageResponse)
@limiter.limit("5/minute")
async def confirm_password_reset(
    request: Request,
    confirm_request: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Confirm password reset with OTP and set new password.

    This is a public endpoint - no authentication required.
    User provides email, OTP, and new password.

    Steps:
    1. Find user by email
    2. Find valid OTP token
    3. Verify OTP matches and hasn't expired
    4. Hash new password
    5. Update user's password
    6. Mark OTP as used
    7. Send confirmation email

    Args:
        request: Password reset confirmation with email, OTP, and new password
        db: Database session

    Returns:
        Success message

    Raises:
        400 Bad Request: If OTP is invalid, expired, or already used
        404 Not Found: If email doesn't exist
    """
    from app.models.password_reset import PasswordResetToken
    from app.utils.email import email_service
    from app.config import settings
    from datetime import datetime, timezone

    # Find user by email
    user = db.query(User).filter(User.email == confirm_request.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Development mode: Allow fixed bypass OTP
    is_dev_bypass = False
    if settings.debug and confirm_request.otp == settings.dev_otp_bypass:
        is_dev_bypass = True
        # No need to check database for dev bypass OTP

    if not is_dev_bypass:
        # Production flow: Find valid OTP token in database
        reset_token = db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.token == confirm_request.otp,
            PasswordResetToken.is_used == False
        ).first()

        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or already used OTP code"
            )

        # Check if token has expired
        if reset_token.is_expired():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP code has expired. Please request a new one."
            )
    else:
        # Dev bypass mode - create dummy token reference
        reset_token = None

    # Update user's password
    user.hashed_password = hash_password(confirm_request.new_password)

    # Mark token as used (skip for dev bypass)
    if reset_token:
        reset_token.is_used = True
        reset_token.used_at = datetime.now(timezone.utc)

    db.commit()

    # Send confirmation email
    await email_service.send_password_changed_notification(
        to_email=user.email,
        username=user.username
    )

    return MessageResponse(
        message="Password successfully reset",
        detail="You can now log in with your new password."
    )


@router.post("/password/change", response_model=MessageResponse)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    password_change: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Change password (requires current password).

    This is a protected endpoint - requires authentication.
    User must provide their current password to change it.

    Steps:
    1. Verify current password is correct
    2. Hash new password
    3. Update user's password
    4. Send confirmation email

    Args:
        request: Password change request with current and new password
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Success message

    Raises:
        400 Bad Request: If current password is incorrect
    """
    from app.utils.email import email_service

    # Verify current password
    if not verify_password(password_change.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Check if new password is different from current
    if password_change.current_password == password_change.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )

    # Update password
    current_user.hashed_password = hash_password(password_change.new_password)
    db.commit()

    # Send confirmation email
    await email_service.send_password_changed_notification(
        to_email=current_user.email,
        username=current_user.username
    )

    return MessageResponse(
        message="Password successfully changed",
        detail="Your password has been updated."
    )


# =============================================================================
# DEVELOPMENT MODE ENDPOINTS
# Only registered when DEBUG=true — routes do not exist in production
# =============================================================================

from app.config import settings as _settings

if _settings.debug:
    @router.get("/dev/get-otp/{email}", response_model=DevOTPResponse)
    async def get_otp_for_email(
        email: str,
        db: Session = Depends(get_db)
    ):
        """Get the latest OTP for a given email (DEVELOPMENT ONLY)."""
        from app.models.password_reset import PasswordResetToken

        # Find user by email
        user = db.query(User).filter(User.email == email).first()

        if not user:
            return DevOTPResponse(
                email=email,
                message=f"No user found with email: {email}",
                otp=None,
                expires_at=None
            )

        # Get the latest unused OTP for this user
        latest_token = db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.is_used == False
        ).order_by(PasswordResetToken.created_at.desc()).first()

        if not latest_token:
            return DevOTPResponse(
                email=email,
                message=f"No active OTP found for {email}. Request a password reset first.",
                otp=None,
                expires_at=None
            )

        # Check if expired
        if latest_token.is_expired():
            return DevOTPResponse(
                email=email,
                message=f"Latest OTP has expired. Request a new password reset.",
                otp=latest_token.token,
                expires_at=latest_token.expires_at
            )

        return DevOTPResponse(
            email=email,
            message=f"Active OTP found. Fixed dev bypass OTP is also available: {_settings.dev_otp_bypass}",
            otp=latest_token.token,
            expires_at=latest_token.expires_at
        )


# ============================================================================
# Admin Product Assignment
# ============================================================================

class ProductAssignment(BaseModel):
    """A single product assignment with permission level."""
    product_id: int
    permission_level: str = Field("view", description="Permission level: view, edit, or owner")


class UserProductsUpdate(BaseModel):
    """Schema for setting a user's product assignments."""
    product_assignments: List[ProductAssignment] = Field(..., description="Product assignments with permission levels")


class UserProductResponse(BaseModel):
    """Schema for a user's product assignment."""
    product_id: int
    product_name: str
    permission_level: str
    granted_at: datetime


@router.get("/users/{user_id}/products", response_model=List[UserProductResponse])
async def get_user_products(
    user_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Get product assignments for a user (admin only). Scoped to products the admin has access to."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    permission_service = PermissionService(db)
    admin_products = permission_service.get_accessible_products(current_user.id)
    admin_product_ids = {p.id for p in admin_products}

    permissions = db.query(ProductPermission, CIProduct).join(
        CIProduct, ProductPermission.product_id == CIProduct.id
    ).filter(
        ProductPermission.user_id == user_id,
        ProductPermission.product_id.in_(admin_product_ids),
    ).all()

    results = {
        product.id: UserProductResponse(
            product_id=product.id,
            product_name=product.product_name,
            permission_level=perm.permission_level.value,
            granted_at=perm.granted_at,
        )
        for perm, product in permissions
    }

    # Include implicit OWNER for products the target user created
    created_products = db.query(CIProduct).filter(
        CIProduct.created_by_user_id == user_id,
        CIProduct.status == "active",
        CIProduct.id.in_(admin_product_ids),
    ).all()
    for product in created_products:
        if product.id not in results:
            results[product.id] = UserProductResponse(
                product_id=product.id,
                product_name=product.product_name,
                permission_level="owner",
                granted_at=product.created_at,
            )

    return list(results.values())


@router.put("/users/{user_id}/products", response_model=List[UserProductResponse])
async def set_user_products(
    user_id: int,
    update: UserProductsUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Set product assignments for a user (admin only).

    Only modifies assignments for products the admin has OWNER access to.
    Assignments for other products are left unchanged.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify your own product assignments"
        )

    permission_service = PermissionService(db)

    # Determine which products the admin can assign (OWNER access required)
    admin_owned_ids = set()
    for assignment in update.product_assignments:
        if permission_service.can_access_product(
            current_user.id, assignment.product_id, ProductPermissionLevel.OWNER
        ):
            admin_owned_ids.add(assignment.product_id)

    requested_product_ids = {a.product_id for a in update.product_assignments}
    unauthorized_ids = requested_product_ids - admin_owned_ids
    if unauthorized_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have owner access to product(s): {sorted(unauthorized_ids)}"
        )

    # Parse permission levels
    level_map = {"view": ProductPermissionLevel.VIEW, "edit": ProductPermissionLevel.EDIT, "owner": ProductPermissionLevel.OWNER}
    assignments = {}
    for a in update.product_assignments:
        perm_level = level_map.get(a.permission_level.lower())
        if not perm_level:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permission level '{a.permission_level}' for product {a.product_id}"
            )
        assignments[a.product_id] = perm_level

    # Remove existing permissions for these specific products only
    db.query(ProductPermission).filter(
        ProductPermission.user_id == user_id,
        ProductPermission.product_id.in_(assignments.keys()),
    ).delete(synchronize_session="fetch")
    db.flush()

    # Add new permissions
    for product_id, perm_level in assignments.items():
        product = db.query(CIProduct).filter(CIProduct.id == product_id).first()
        if not product:
            continue
        perm = ProductPermission(
            product_id=product_id,
            user_id=user_id,
            permission_level=perm_level,
            granted_by_user_id=current_user.id,
        )
        db.add(perm)

    db.commit()

    # Return updated assignments (scoped to admin's accessible products)
    admin_products = permission_service.get_accessible_products(current_user.id)
    admin_product_ids = {p.id for p in admin_products}

    permissions = db.query(ProductPermission, CIProduct).join(
        CIProduct, ProductPermission.product_id == CIProduct.id
    ).filter(
        ProductPermission.user_id == user_id,
        ProductPermission.product_id.in_(admin_product_ids),
    ).all()

    results = {
        product.id: UserProductResponse(
            product_id=product.id,
            product_name=product.product_name,
            permission_level=perm.permission_level.value,
            granted_at=perm.granted_at,
        )
        for perm, product in permissions
    }

    created_products = db.query(CIProduct).filter(
        CIProduct.created_by_user_id == user_id,
        CIProduct.status == "active",
        CIProduct.id.in_(admin_product_ids),
    ).all()
    for product in created_products:
        if product.id not in results:
            results[product.id] = UserProductResponse(
                product_id=product.id,
                product_name=product.product_name,
                permission_level="owner",
                granted_at=product.created_at,
            )

    return list(results.values())