"""Tests for MCP OAuth JWT utilities."""

import time
import pytest
from mcp_server.oauth_jwt import (
    mint_access_token,
    verify_access_token,
    ACCESS_TOKEN_EXPIRY_SECONDS,
    TOKEN_ISSUER,
)


class TestMintAccessToken:
    def test_mint_returns_string(self):
        token = mint_access_token(user_id=1, client_id="test-client", scopes=["mcp"])
        assert isinstance(token, str)
        assert len(token) > 0

    def test_mint_different_users_produce_different_tokens(self):
        t1 = mint_access_token(user_id=1, client_id="c", scopes=[])
        t2 = mint_access_token(user_id=2, client_id="c", scopes=[])
        assert t1 != t2


class TestVerifyAccessToken:
    def test_round_trip(self):
        token = mint_access_token(user_id=42, client_id="my-client", scopes=["mcp"])
        result = verify_access_token(token)
        assert result is not None
        assert result.client_id == "my-client"
        assert result.scopes == ["mcp"]
        assert result.expires_at > time.time()

    def test_expired_token_rejected(self):
        token = mint_access_token(user_id=1, client_id="c", scopes=[], expires_in=-1)
        result = verify_access_token(token)
        assert result is None

    def test_invalid_token_rejected(self):
        result = verify_access_token("not-a-valid-jwt")
        assert result is None

    def test_non_mcp_jwt_rejected(self):
        """A valid JWT with wrong issuer should be rejected."""
        from jose import jwt
        from app.config import settings

        payload = {
            "sub": "1",
            "user_id": 1,
            "iss": "not-mcp",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
        result = verify_access_token(token)
        assert result is None

    def test_custom_expiry(self):
        token = mint_access_token(user_id=1, client_id="c", scopes=[], expires_in=10)
        result = verify_access_token(token)
        assert result is not None
        assert result.expires_at <= time.time() + 11
