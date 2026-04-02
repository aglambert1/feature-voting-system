"""
API key authentication provider for the MCP HTTP server.

Validates Bearer tokens (API keys) against the user_api_keys table.
Uses FastMCP's built-in AuthProvider interface so the framework handles
all HTTP auth middleware wiring automatically.
"""

import logging
from datetime import datetime

from fastmcp.server.auth import TokenVerifier, AccessToken

from app.models.api_key import UserAPIKey
from app.utils.security import pwd_context
from mcp_server.db import get_session

logger = logging.getLogger(__name__)


class APIKeyAuthProvider(TokenVerifier):
    """Validates Feature-IQ API keys (fiq_...) for MCP HTTP access.

    Used as a fallback verifier in MultiAuth alongside the OAuth provider.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify an API key and return access info if valid.

        Flow:
        1. Extract prefix (fiq_ + first 8 chars) for fast index lookup
        2. Query candidates by prefix (not revoked, not expired)
        3. bcrypt-verify full token against matches (usually 0-1)
        4. Update last_used_at timestamp
        5. Return AccessToken with user_id in claims
        """
        if not token.startswith("fiq_"):
            return None

        prefix = token[:12]  # "fiq_" + 8 chars

        try:
            with get_session() as db:
                candidates = (
                    db.query(UserAPIKey)
                    .filter(
                        UserAPIKey.key_prefix == prefix,
                        UserAPIKey.is_revoked.is_(False),
                        UserAPIKey.expires_at > datetime.utcnow(),
                    )
                    .all()
                )

                for candidate in candidates:
                    if pwd_context.verify(token, candidate.key_hash):
                        candidate.last_used_at = datetime.utcnow()
                        user_id = candidate.user_id
                        logger.info(
                            "MCP API key authenticated: user_id=%d, key=%s",
                            user_id,
                            prefix,
                        )
                        return AccessToken(
                            token=token,
                            client_id=str(user_id),
                            scopes=[],
                            claims={"user_id": user_id},
                        )

        except Exception:
            logger.exception("Error validating API key")

        return None
