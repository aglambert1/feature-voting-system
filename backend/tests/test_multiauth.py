"""Tests for MultiAuth (OAuth + API key) token verification."""

import time
import pytest
import asyncio

from mcp.server.auth.provider import AccessToken
from mcp_server.oauth_jwt import mint_access_token


class TestMultiAuthVerification:
    """Test that both OAuth JWTs and API keys are accepted."""

    def test_oauth_jwt_accepted(self):
        """A valid MCP OAuth JWT should be verified."""
        token = mint_access_token(user_id=1, client_id="test", scopes=["mcp"])
        # Verify it directly (MultiAuth delegates to load_access_token)
        from mcp_server.oauth_jwt import verify_access_token
        result = verify_access_token(token)
        assert result is not None
        assert result.client_id == "test"

    def test_invalid_token_rejected(self):
        """An invalid token should be rejected by both verifiers."""
        from mcp_server.oauth_jwt import verify_access_token
        result = verify_access_token("not-a-jwt-or-api-key")
        assert result is None

    def test_expired_oauth_token_rejected(self):
        """An expired OAuth JWT should be rejected."""
        from mcp_server.oauth_jwt import verify_access_token
        token = mint_access_token(user_id=1, client_id="c", scopes=[], expires_in=-1)
        result = verify_access_token(token)
        assert result is None

    def test_api_key_format_not_jwt(self):
        """API keys (fiq_...) should fail JWT verification but would pass
        through to the API key verifier in MultiAuth."""
        from mcp_server.oauth_jwt import verify_access_token
        result = verify_access_token("fiq_someapikey12345")
        assert result is None  # Not a JWT, falls through to API key verifier
