"""
Pydantic schemas for authentication.

Schemas are used to:
1. Validate incoming data (requests)
2. Serialize outgoing data (responses)
3. Provide automatic API documentation

The difference between a Model and a Schema:
- Model = Database structure (SQLAlchemy)
- Schema = API data structure (Pydantic)
"""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from app.models.user import UserRole


class UserCreate(BaseModel):
    """
    Schema for creating a new user (registration).

    This is what the API expects when someone registers.
    Note: role is NOT included here - new users always start as VOTER.
    Only admins can change roles via a separate endpoint.
    """
    email: EmailStr  # EmailStr automatically validates email format
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """
    Schema for logging in.

    User can login with either email or username + password.
    """
    username: str  # Can be email or username
    password: str


class UserResponse(BaseModel):
    """
    Schema for returning user information.

    This is what the API sends back when you request user info.
    NOTE: We never send the password back!
    """
    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        """
        Pydantic configuration.

        from_attributes=True allows Pydantic to work with SQLAlchemy models.
        This means you can do: UserResponse.from_orm(db_user)
        """
        from_attributes = True


class Token(BaseModel):
    """
    Schema for JWT token response.

    This is returned after successful login.
    """
    access_token: str
    token_type: str = "bearer"  # Always "bearer" for JWT


class TokenData(BaseModel):
    """
    Schema for data stored inside the JWT token.

    When we decode a token, we get this data back.
    """
    username: Optional[str] = None
    user_id: Optional[int] = None


class UserRoleUpdate(BaseModel):
    """
    Schema for updating a user's role.

    Only admins can use this to change user roles.
    """
    role: UserRole
