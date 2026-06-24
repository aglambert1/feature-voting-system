"""
Security utilities for password hashing and JWT token management.

This file handles:
1. Hashing passwords before storing them
2. Verifying passwords when users log in
3. Creating JWT tokens for authentication
4. Verifying JWT tokens from requests
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.auth import TokenData


# OAuth2 scheme for token authentication
# tokenUrl="auth/login" tells FastAPI where to get tokens from
# This is used in the automatic API docs (/docs)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dictionary of data to encode in the token (usually user info)
        expires_delta: How long until the token expires (optional)

    Returns:
        The encoded JWT token as a string

    Example:
        token = create_access_token(
            data={"sub": user.username, "user_id": user.id}
        )
    """
    # Make a copy of the data so we don't modify the original
    to_encode = data.copy()

    # Set expiration time
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default expiration from settings (usually 30 minutes)
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc).timestamp(),
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm
    )

    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the current user from a JWT token.

    This is used as a dependency in routes that require authentication:
        @app.get("/protected")
        def protected_route(current_user: User = Depends(get_current_user)):
            return {"message": f"Hello {current_user.username}"}

    Args:
        token: The JWT token from the request header
        db: Database session

    Returns:
        The User object for the authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    # Exception to raise if authentication fails
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )

        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        token_data = TokenData(username=username)

    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == token_data.username).first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    if user.tokens_valid_after:
        iat = payload.get("iat")
        if iat is not None:
            issued_at = datetime.fromtimestamp(iat, tz=timezone.utc)
            valid_after = user.tokens_valid_after
            if valid_after.tzinfo is None:
                valid_after = valid_after.replace(tzinfo=timezone.utc)
            if issued_at < valid_after:
                raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Ensure the current user is active.

    This is an extra layer on top of get_current_user.
    Use this in routes that should only be accessible to active users.

    Args:
        current_user: The user from get_current_user

    Returns:
        The User object if active

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Verify that the current user is an admin.

    Args:
        current_user: The authenticated user

    Returns:
        The admin user

    Raises:
        403 Forbidden: If user is not an admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required."
        )
    return current_user


async def get_product_owner_or_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Verify that the current user is either a Product Owner or Admin.

    Product Owners can manage products and competitive intelligence.
    Admins have full system access.

    Args:
        current_user: The authenticated user

    Returns:
        The user if they are a Product Owner or Admin

    Raises:
        403 Forbidden: If user is not a Product Owner or Admin
    """
    if current_user.role not in [UserRole.PRODUCT_OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Product Owners and Admins can access this resource"
        )
    return current_user