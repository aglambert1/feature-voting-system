"""
JWT utilities for MCP OAuth access tokens.

Mints and verifies HS256 JWTs used as OAuth access tokens.
Uses the same secret key as the main FastAPI app.
Access tokens are stateless — no DB lookup needed on verification.
"""

import time
from typing import Optional

from jose import jwt, JWTError
from mcp.server.auth.provider import AccessToken

from app.config import settings

# Access tokens expire after 1 hour
ACCESS_TOKEN_EXPIRY_SECONDS = 60 * 60

# Issuer claim to distinguish MCP OAuth tokens from main app JWTs
TOKEN_ISSUER = "feature-iq-mcp"


def mint_access_token(
    user_id: int,
    client_id: str,
    scopes: list[str],
    expires_in: int = ACCESS_TOKEN_EXPIRY_SECONDS,
) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: The authenticated user's ID.
        client_id: The OAuth client that requested the token.
        scopes: Granted OAuth scopes.
        expires_in: Token lifetime in seconds (default 1 hour).

    Returns:
        Encoded JWT string.
    """
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "client_id": client_id,
        "scopes": scopes,
        "iss": TOKEN_ISSUER,
        "iat": now,
        "exp": now + expires_in,
        "user_id": user_id,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def verify_access_token_claims(token: str) -> dict:
    """Decode JWT payload and return the full claims dict.

    Returns empty dict if the token is invalid or not an MCP token.
    Used by user_context.py to extract user_id from the token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_exp": True},
        )
        if payload.get("iss") != TOKEN_ISSUER:
            return {}
        return payload
    except JWTError:
        return {}


def verify_access_token(token: str) -> Optional[AccessToken]:
    """Decode and verify a JWT access token.

    Returns an AccessToken if valid, None if expired/invalid.
    No database lookup — purely cryptographic verification.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_exp": True},
        )

        # Must be an MCP OAuth token (not a main app session JWT)
        if payload.get("iss") != TOKEN_ISSUER:
            return None

        return AccessToken(
            token=token,
            client_id=payload.get("client_id", ""),
            scopes=payload.get("scopes", []),
            expires_at=payload.get("exp", 0),
        )
    except JWTError:
        return None
