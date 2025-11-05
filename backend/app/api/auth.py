"""
Authentication routes.

This file contains all endpoints related to user authentication:
- POST /auth/register - Create a new user account
- POST /auth/login - Log in and get an access token
- GET /auth/me - Get current user information
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    Token,
    UserRoleUpdate,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordChange,
    MessageResponse
)
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_active_user,
    get_current_admin_user
)


# Create a router for authentication endpoints
# All routes in this file will be prefixed with /auth
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account.

    Steps:
    1. Check if email or username already exists
    2. Hash the password
    3. Create new user in database
    4. Return user information (without password)

    Args:
        user_data: User registration data (email, username, password)
        db: Database session (automatically provided by FastAPI)

    Returns:
        The newly created user information

    Raises:
        400 Bad Request: If email or username already exists
    """
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
    # Note: role defaults to VOTER (set in the User model)
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name
    )

    # Add to database and commit
    db.add(new_user)
    db.commit()
    db.refresh(new_user)  # Refresh to get the auto-generated ID

    return new_user


@router.post("/login", response_model=Token)
def login(
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


@router.post("/password/reset-request", response_model=MessageResponse)
async def request_password_reset(
    request: PasswordResetRequest,
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
    from datetime import datetime

    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()

    # Security consideration: Don't reveal if email exists or not
    # Always return success, but only send email if user exists
    if not user:
        # Return success even if user doesn't exist (prevents email enumeration)
        return MessageResponse(
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

    return MessageResponse(
        message="If this email is registered, you will receive a password reset code.",
        detail="Check your email for the OTP code. It expires in 15 minutes."
    )


@router.post("/password/reset-confirm", response_model=MessageResponse)
async def confirm_password_reset(
    request: PasswordResetConfirm,
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
    from datetime import datetime

    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Find valid OTP token
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.token == request.otp,
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

    # Update user's password
    user.hashed_password = hash_password(request.new_password)

    # Mark token as used
    reset_token.is_used = True
    reset_token.used_at = datetime.utcnow()

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
async def change_password(
    request: PasswordChange,
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
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Check if new password is different from current
    if request.current_password == request.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )

    # Update password
    current_user.hashed_password = hash_password(request.new_password)
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