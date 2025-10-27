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
from app.schemas.auth import UserCreate, UserLogin, UserResponse, Token, UserRoleUpdate
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