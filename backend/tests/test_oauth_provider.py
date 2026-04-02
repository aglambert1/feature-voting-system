"""Tests for the Feature-IQ OAuth provider."""

import time
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
import app.models  # noqa: F401 — register all models

from mcp_server.oauth_provider import (
    FeatureIQOAuthProvider,
    _hash_token,
    AUTH_CODE_EXPIRY_SECONDS,
)
from mcp_server.oauth_models import OAuthClient, OAuthAuthorizationCode, OAuthRefreshToken
from mcp_server.oauth_jwt import mint_access_token

from mcp.server.auth.provider import AuthorizationParams, AuthorizationCode, TokenError
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyHttpUrl


@pytest.fixture
def db_engine():
    """In-memory SQLite engine with all tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def provider():
    return FeatureIQOAuthProvider(
        base_url="http://localhost:8001",
        frontend_url="http://localhost:5173",
    )


@pytest.fixture
def test_user(db_session):
    """Create a test user for OAuth consent flow."""
    from app.models.user import User, UserRole
    user = User(
        email="oauth@test.com",
        username="oauthuser",
        hashed_password="hashed",
        full_name="OAuth Test User",
        role=UserRole.VOTER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_get_session(db_engine):
    """Mock get_session to use our test database.

    Uses the same engine/connection so all sessions share state.
    """
    from contextlib import contextmanager

    @contextmanager
    def _get_session():
        Session = sessionmaker(bind=db_engine)
        session = Session()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    with patch("mcp_server.oauth_provider.get_session", _get_session):
        yield


@pytest.fixture
def sample_client_info():
    return OAuthClientInformationFull(
        client_id="test-client-123",
        client_name="Test MCP Client",
        redirect_uris=[AnyHttpUrl("http://localhost:9999/callback")],
        grant_types=["authorization_code"],
        response_types=["code"],
        token_endpoint_auth_method="none",
        scope="mcp",
    )


def run_async(coro):
    """Helper to run async methods in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestClientRegistration:
    def test_register_and_get_client(self, provider, mock_get_session, sample_client_info):
        run_async(provider.register_client(sample_client_info))
        client = run_async(provider.get_client("test-client-123"))
        assert client is not None
        assert client.client_id == "test-client-123"
        assert client.client_name == "Test MCP Client"

    def test_get_nonexistent_client(self, provider, mock_get_session):
        client = run_async(provider.get_client("nonexistent"))
        assert client is None

    def test_re_registration_is_idempotent(self, provider, mock_get_session, sample_client_info):
        run_async(provider.register_client(sample_client_info))
        run_async(provider.register_client(sample_client_info))  # Should not raise
        client = run_async(provider.get_client("test-client-123"))
        assert client is not None


class TestAuthorization:
    def test_authorize_returns_consent_url(self, provider, mock_get_session, sample_client_info, test_user):
        run_async(provider.register_client(sample_client_info))

        params = AuthorizationParams(
            state="test-state",
            scopes=["mcp"],
            code_challenge="test-challenge-value",
            redirect_uri=AnyHttpUrl("http://localhost:9999/callback"),
            redirect_uri_provided_explicitly=True,
        )

        redirect_url = run_async(provider.authorize(sample_client_info, params))
        assert "oauth/login" in redirect_url
        assert "txn_id=" in redirect_url
        assert "client_name=" in redirect_url


class TestTokenExchange:
    def test_exchange_authorization_code(self, provider, mock_get_session, db_session, sample_client_info, test_user):
        run_async(provider.register_client(sample_client_info))

        # Manually create an auth code with user_id set (simulating consent)
        code = "test-auth-code-xyz"
        db_session.add(OAuthAuthorizationCode(
            code=code,
            client_id="test-client-123",
            user_id=test_user.id,
            redirect_uri="http://localhost:9999/callback",
            redirect_uri_provided_explicitly=True,
            scopes=["mcp"],
            code_challenge="challenge",
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            consumed=False,
        ))
        db_session.commit()

        auth_code = AuthorizationCode(
            code=code,
            client_id="test-client-123",
            scopes=["mcp"],
            expires_at=time.time() + 300,
            code_challenge="challenge",
            redirect_uri=AnyHttpUrl("http://localhost:9999/callback"),
            redirect_uri_provided_explicitly=True,
        )

        token = run_async(provider.exchange_authorization_code(sample_client_info, auth_code))
        assert token.access_token
        assert token.refresh_token
        assert token.token_type == "Bearer"
        assert token.expires_in > 0

    def test_exchange_consumed_code_fails(self, provider, mock_get_session, db_session, sample_client_info, test_user):
        run_async(provider.register_client(sample_client_info))

        code = "consumed-code"
        db_session.add(OAuthAuthorizationCode(
            code=code,
            client_id="test-client-123",
            user_id=test_user.id,
            redirect_uri="http://localhost:9999/callback",
            redirect_uri_provided_explicitly=True,
            scopes=["mcp"],
            code_challenge="challenge",
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            consumed=True,
        ))
        db_session.commit()

        auth_code = AuthorizationCode(
            code=code,
            client_id="test-client-123",
            scopes=["mcp"],
            expires_at=time.time() + 300,
            code_challenge="challenge",
            redirect_uri=AnyHttpUrl("http://localhost:9999/callback"),
            redirect_uri_provided_explicitly=True,
        )

        with pytest.raises((TokenError, Exception)):
            run_async(provider.exchange_authorization_code(sample_client_info, auth_code))


class TestAccessToken:
    def test_load_valid_jwt(self, provider):
        token = mint_access_token(user_id=1, client_id="c", scopes=["mcp"])
        result = run_async(provider.load_access_token(token))
        assert result is not None
        assert result.client_id == "c"

    def test_load_invalid_token(self, provider):
        result = run_async(provider.load_access_token("invalid"))
        assert result is None


class TestRefreshToken:
    def test_load_valid_refresh_token(self, provider, mock_get_session, db_session, sample_client_info, test_user):
        run_async(provider.register_client(sample_client_info))

        raw_token = "raw-refresh-token-value"
        token_hash = _hash_token(raw_token)
        db_session.add(OAuthRefreshToken(
            token_hash=token_hash,
            client_id="test-client-123",
            user_id=test_user.id,
            scopes=["mcp"],
            expires_at=datetime.utcnow() + timedelta(days=30),
            is_revoked=False,
        ))
        db_session.commit()

        result = run_async(provider.load_refresh_token(sample_client_info, raw_token))
        assert result is not None
        assert result.client_id == "test-client-123"

    def test_load_revoked_refresh_token(self, provider, mock_get_session, db_session, sample_client_info, test_user):
        run_async(provider.register_client(sample_client_info))

        raw_token = "revoked-token"
        db_session.add(OAuthRefreshToken(
            token_hash=_hash_token(raw_token),
            client_id="test-client-123",
            user_id=test_user.id,
            scopes=["mcp"],
            expires_at=datetime.utcnow() + timedelta(days=30),
            is_revoked=True,
        ))
        db_session.commit()

        result = run_async(provider.load_refresh_token(sample_client_info, raw_token))
        assert result is None
