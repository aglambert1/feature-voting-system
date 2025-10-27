"""
Pydantic schemas package.

Schemas define the shape of data coming in and out of the API.
"""

from app.schemas.auth import UserCreate, UserLogin, UserResponse, Token

__all__ = ["UserCreate", "UserLogin", "UserResponse", "Token"]
