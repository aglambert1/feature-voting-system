"""
API key model for MCP HTTP server authentication.

API keys allow Product Owners to connect external MCP clients
(Claude Desktop, Cursor, Claude Code) to the Feature-IQ MCP server.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class UserAPIKey(Base):
    """API key for authenticating MCP HTTP connections."""

    __tablename__ = "user_api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_hash = Column(String, nullable=False)
    key_prefix = Column(String(12), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    is_revoked = Column(Boolean, default=False, nullable=False)

    user = relationship("User", backref="api_keys")

    def __repr__(self):
        return f"<UserAPIKey(id={self.id}, prefix='{self.key_prefix}', name='{self.name}')>"

    def to_dict(self):
        return {
            "id": self.id,
            "key_prefix": self.key_prefix,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "is_revoked": self.is_revoked,
        }
