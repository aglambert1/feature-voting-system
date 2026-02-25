"""
Product invite code model for database.

Stores invite codes that POs generate to invite voters to their products.
Voters redeem codes during registration or via /join/:code to gain product access.
"""

import secrets
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.competitor_intelligence import ProductPermissionLevel


class ProductInviteCode(Base):
    """
    Invite code for granting product access.

    POs create codes scoped to a single product. Voters redeem them to get
    a ProductPermission row. Codes can be multi-use (shared link) or
    limited to a specific number of uses.
    """

    __tablename__ = "product_invite_codes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("ci_products.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    max_uses = Column(Integer, nullable=True)  # null = unlimited
    current_uses = Column(Integer, default=0, nullable=False)
    permission_level = Column(Enum(ProductPermissionLevel), default=ProductPermissionLevel.VIEW, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # null = no expiration
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    product = relationship("CIProduct")
    created_by = relationship("User")

    @staticmethod
    def generate_code() -> str:
        """Generate a URL-safe invite code."""
        return secrets.token_urlsafe(16)

    def is_expired(self) -> bool:
        """Check if this code has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def is_at_max_uses(self) -> bool:
        """Check if this code has reached its usage limit."""
        if self.max_uses is None:
            return False
        return self.current_uses >= self.max_uses

    def is_valid(self) -> bool:
        """Check if this code can be redeemed."""
        return self.is_active and not self.is_expired() and not self.is_at_max_uses()

    def __repr__(self):
        return f"<ProductInviteCode(id={self.id}, product_id={self.product_id}, code='{self.code[:8]}...', valid={self.is_valid()})>"
