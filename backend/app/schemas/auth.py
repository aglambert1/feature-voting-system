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
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional, List

from app.models.user import UserRole


class UserCreate(BaseModel):
    """
    Schema for creating a new user (registration).

    Two modes:
    1. Self-registration: invite_code is required, product access is derived from the code
    2. Admin-created: role and product_ids can be specified, invite_code not needed
    """
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    invite_code: Optional[str] = Field(None, description="Required for self-registration")
    product_ids: Optional[List[int]] = Field(None, description="Product assignments (admin-created users only)")


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
    has_seen_welcome: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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


class ProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=200)


class UserRoleUpdate(BaseModel):
    """
    Schema for updating a user's role.

    Only admins can use this to change user roles.
    """
    role: UserRole


class PasswordResetRequest(BaseModel):
    """
    Schema for requesting a password reset.

    User provides their email and we send them an OTP.
    """
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """
    Schema for confirming password reset with OTP.

    User provides the OTP they received via email and their new password.
    """
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str = Field(..., min_length=8, max_length=100)


class PasswordChange(BaseModel):
    """
    Schema for changing password (requires current password).

    User must provide their current password to change it.
    """
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


class MessageResponse(BaseModel):
    """
    Schema for simple message responses.

    Used for success/info messages.
    """
    message: str
    detail: Optional[str] = None


class PasswordResetResponse(BaseModel):
    """
    Schema for password reset request response.

    In production: Only contains message and detail.
    In development (debug=True): Can also include the OTP for testing.
    """
    message: str
    detail: Optional[str] = None
    dev_otp: Optional[str] = Field(
        None,
        description="OTP code (only returned in development mode)"
    )


class DevOTPResponse(BaseModel):
    """
    Schema for development-only OTP retrieval.

    WARNING: This should only be used in development environments!
    """
    email: str
    otp: Optional[str] = None
    expires_at: Optional[datetime] = None
    message: str
