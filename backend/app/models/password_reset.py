"""
Password reset token model for database.

This stores OTP (One-Time Password) tokens for password reset functionality.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class PasswordResetToken(Base):
    """
    Model for storing password reset tokens (OTPs).

    When a user requests password reset:
    1. Generate a random OTP code
    2. Store it in this table with expiration time
    3. Send OTP to user's email
    4. User provides OTP to reset password
    5. Verify OTP is valid and not expired
    6. Mark as used after successful reset
    """

    __tablename__ = "password_reset_tokens"

    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # User this token belongs to
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # The OTP code (6-digit number, stored as string)
    token = Column(String, nullable=False, index=True)

    # When the token expires (typically 10-15 minutes)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Has this token been used already?
    is_used = Column(Boolean, default=False, nullable=False)

    # When was this token created
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # When was this token used (if at all)
    used_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship to user
    user = relationship("User")

    def is_expired(self) -> bool:
        """Check if this token has expired."""
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expires

    def is_valid(self) -> bool:
        """Check if this token is valid (not used and not expired)."""
        return not self.is_used and not self.is_expired()

    def __repr__(self):
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id}, valid={self.is_valid()})>"
