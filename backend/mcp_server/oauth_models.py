"""
OAuth 2.1 database models for MCP HTTP server authentication.

Stores OAuth clients (from Dynamic Client Registration),
authorization codes (short-lived, PKCE), and refresh tokens.
Access tokens are JWTs and not stored in the database.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import func

from app.database import Base


class OAuthClient(Base):
    """Registered OAuth client (from Dynamic Client Registration)."""

    __tablename__ = "oauth_clients"

    client_id = Column(String, primary_key=True)
    client_secret_hash = Column(String, nullable=True)
    client_name = Column(String(200), nullable=True)
    redirect_uris = Column(JSON, nullable=False, default=list)
    grant_types = Column(JSON, nullable=False, default=list)
    response_types = Column(JSON, nullable=False, default=list)
    token_endpoint_auth_method = Column(String(50), nullable=False, default="none")
    scope = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<OAuthClient(client_id='{self.client_id}', name='{self.client_name}')>"


class OAuthAuthorizationCode(Base):
    """Short-lived authorization code for OAuth code exchange.

    Expires after 5 minutes. Single-use (consumed flag).
    Stores PKCE code_challenge for verification during token exchange.
    """

    __tablename__ = "oauth_authorization_codes"

    code = Column(String, primary_key=True)
    client_id = Column(String, ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)  # Set when user approves consent
    redirect_uri = Column(Text, nullable=False)
    redirect_uri_provided_explicitly = Column(Boolean, nullable=False, default=True)
    scopes = Column(JSON, nullable=False, default=list)
    code_challenge = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<OAuthAuthorizationCode(code='{self.code[:8]}...', client_id='{self.client_id}')>"


class OAuthRefreshToken(Base):
    """Long-lived refresh token for obtaining new access tokens.

    Stored as SHA-256 hash of the opaque token value.
    Expires after 30 days. Supports revocation.
    """

    __tablename__ = "oauth_refresh_tokens"

    token_hash = Column(String, primary_key=True)
    client_id = Column(String, ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scopes = Column(JSON, nullable=False, default=list)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<OAuthRefreshToken(hash='{self.token_hash[:8]}...', client_id='{self.client_id}')>"
