"""
Feature-IQ OAuth 2.1 provider for MCP HTTP server.

Implements the 9 required OAuthProvider methods backed by PostgreSQL.
Access tokens are stateless JWTs; refresh tokens and auth codes are
stored in the database.

Reference: fastmcp/server/auth/providers/in_memory.py
"""

import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyHttpUrl

from fastmcp.server.auth.auth import (
    ClientRegistrationOptions,
    OAuthProvider,
    RevocationOptions,
)

from app.config import settings
from mcp_server.db import get_session
from mcp_server.oauth_jwt import (
    ACCESS_TOKEN_EXPIRY_SECONDS,
    mint_access_token,
    verify_access_token,
)
from mcp_server.oauth_models import (
    OAuthAuthorizationCode,
    OAuthClient,
    OAuthRefreshToken,
)

logger = logging.getLogger(__name__)

# Authorization codes expire after 5 minutes
AUTH_CODE_EXPIRY_SECONDS = 5 * 60

# Refresh tokens expire after 30 days
REFRESH_TOKEN_EXPIRY_SECONDS = 30 * 24 * 60 * 60


def _hash_token(token: str) -> str:
    """SHA-256 hash a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


class FeatureIQOAuthProvider(OAuthProvider):
    """OAuth provider backed by PostgreSQL.

    - Clients stored in oauth_clients table (Dynamic Client Registration)
    - Auth codes stored in oauth_authorization_codes table (5 min TTL)
    - Refresh tokens stored as SHA-256 hashes in oauth_refresh_tokens table
    - Access tokens are JWTs (not stored, verified by signature)
    """

    def __init__(
        self,
        base_url: str,
        frontend_url: str = "http://localhost:5173",
    ):
        super().__init__(
            base_url=base_url,
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=["mcp"],
            ),
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=[],
        )
        self.frontend_url = frontend_url.rstrip("/")

    # ---- Client Registration ----

    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        # Extract redirect_uri from the current request if available
        # (needed to auto-register clients that skip /register)
        from fastmcp.server.http import _current_http_request
        request_redirect_uri = None
        request = _current_http_request.get(None)
        if request:
            request_redirect_uri = request.query_params.get("redirect_uri")

        with get_session() as db:
            row = db.query(OAuthClient).filter(OAuthClient.client_id == client_id).first()
            if not row:
                # Auto-register unknown clients (e.g., mcp-remote generates its
                # own client_id without calling /register)
                logger.info("Auto-registering unknown client: %s", client_id)
                redirect_uris = [request_redirect_uri] if request_redirect_uri else ["http://localhost"]
                row = OAuthClient(
                    client_id=client_id,
                    client_name="MCP Client",
                    redirect_uris=redirect_uris,
                    grant_types=["authorization_code", "refresh_token"],
                    response_types=["code"],
                    token_endpoint_auth_method="none",
                    scope="mcp",
                )
                db.add(row)
            else:
                # Ensure the redirect_uri from this request is registered
                if request_redirect_uri:
                    uris = list(row.redirect_uris or [])
                    if request_redirect_uri not in uris:
                        uris.append(request_redirect_uri)
                        row.redirect_uris = uris

            redirect_uris = row.redirect_uris or []
            if request_redirect_uri and request_redirect_uri not in redirect_uris:
                redirect_uris = redirect_uris + [request_redirect_uri]

            return OAuthClientInformationFull(
                client_id=row.client_id,
                client_secret=None,
                client_name=row.client_name,
                redirect_uris=redirect_uris if redirect_uris else ["http://localhost"],
                grant_types=row.grant_types or [],
                response_types=row.response_types or [],
                token_endpoint_auth_method=row.token_endpoint_auth_method or "none",
                scope=row.scope,
            )

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if self.client_registration_options and self.client_registration_options.valid_scopes:
            if client_info.scope:
                requested = set(client_info.scope.split())
                valid = set(self.client_registration_options.valid_scopes)
                invalid = requested - valid
                if invalid:
                    raise ValueError(f"Invalid scopes: {', '.join(invalid)}")

        with get_session() as db:
            existing = db.query(OAuthClient).filter(
                OAuthClient.client_id == client_info.client_id
            ).first()
            if existing:
                return  # Re-registration is OK per RFC 7591

            client = OAuthClient(
                client_id=client_info.client_id,
                client_secret_hash=None,
                client_name=client_info.client_name,
                redirect_uris=[str(u) for u in (client_info.redirect_uris or [])],
                grant_types=client_info.grant_types or [],
                response_types=client_info.response_types or [],
                token_endpoint_auth_method=client_info.token_endpoint_auth_method or "none",
                scope=client_info.scope,
            )
            db.add(client)

    # ---- Authorization ----

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Store auth code and redirect to login page on the MCP server.

        The login page authenticates the user, binds them to the auth code,
        and redirects to the client's redirect_uri with the code.
        """
        if not client.client_id:
            raise AuthorizeError(error="invalid_client", error_description="Client ID required")

        code_value = secrets.token_urlsafe(32)
        expires_at = time.time() + AUTH_CODE_EXPIRY_SECONDS
        scopes = params.scopes or []

        with get_session() as db:
            auth_code = OAuthAuthorizationCode(
                code=code_value,
                client_id=client.client_id,
                user_id=None,  # Set when user logs in
                redirect_uri=str(params.redirect_uri),
                redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
                scopes=scopes,
                code_challenge=params.code_challenge,
                expires_at=datetime.utcfromtimestamp(expires_at),
                consumed=False,
            )
            db.add(auth_code)

        # Redirect to login page served by this MCP server
        from urllib.parse import urlencode, quote
        login_params = urlencode({
            "txn_id": code_value,
            "client_name": client.client_name or "MCP Client",
            "state": params.state or "",
        })
        base = str(self.base_url).rstrip("/")
        return f"{base}/oauth/login?{login_params}"

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> Optional[AuthorizationCode]:
        with get_session() as db:
            row = db.query(OAuthAuthorizationCode).filter(
                OAuthAuthorizationCode.code == authorization_code
            ).first()

            if not row:
                return None
            if row.client_id != client.client_id:
                return None
            if row.consumed:
                return None
            if row.expires_at < datetime.utcnow():
                return None
            if row.user_id is None:
                # User hasn't approved consent yet
                return None

            return AuthorizationCode(
                code=row.code,
                client_id=row.client_id,
                scopes=row.scopes or [],
                expires_at=row.expires_at.timestamp(),
                code_challenge=row.code_challenge,
                redirect_uri=AnyHttpUrl(row.redirect_uri),
                redirect_uri_provided_explicitly=row.redirect_uri_provided_explicitly,
            )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        # Mark code as consumed
        with get_session() as db:
            row = db.query(OAuthAuthorizationCode).filter(
                OAuthAuthorizationCode.code == authorization_code.code
            ).first()
            if not row or row.consumed:
                raise TokenError("invalid_grant", "Authorization code not found or already used.")

            user_id = row.user_id
            row.consumed = True

        # Mint JWT access token
        access_token_value = mint_access_token(
            user_id=user_id,
            client_id=client.client_id or "",
            scopes=authorization_code.scopes,
        )

        # Generate opaque refresh token and store hash
        refresh_token_value = secrets.token_urlsafe(48)
        refresh_hash = _hash_token(refresh_token_value)
        refresh_expires = datetime.utcnow() + timedelta(seconds=REFRESH_TOKEN_EXPIRY_SECONDS)

        with get_session() as db:
            db.add(OAuthRefreshToken(
                token_hash=refresh_hash,
                client_id=client.client_id or "",
                user_id=user_id,
                scopes=authorization_code.scopes,
                expires_at=refresh_expires,
                is_revoked=False,
            ))

        logger.info("OAuth tokens issued: user_id=%d, client_id=%s", user_id, client.client_id)

        return OAuthToken(
            access_token=access_token_value,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_EXPIRY_SECONDS,
            refresh_token=refresh_token_value,
            scope=" ".join(authorization_code.scopes),
        )

    # ---- Token Verification ----

    async def load_access_token(self, token: str) -> Optional[AccessToken]:
        """Verify JWT access token. No DB lookup needed."""
        return verify_access_token(token)

    # ---- Refresh Tokens ----

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> Optional[RefreshToken]:
        token_hash = _hash_token(refresh_token)

        with get_session() as db:
            row = db.query(OAuthRefreshToken).filter(
                OAuthRefreshToken.token_hash == token_hash
            ).first()

            if not row:
                return None
            if row.client_id != client.client_id:
                return None
            if row.is_revoked:
                return None
            if row.expires_at < datetime.utcnow():
                row.is_revoked = True
                return None

            return RefreshToken(
                token=refresh_token,
                client_id=row.client_id,
                scopes=row.scopes or [],
                expires_at=int(row.expires_at.timestamp()),
            )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        # Validate scopes
        original_scopes = set(refresh_token.scopes)
        requested_scopes = set(scopes)
        if not requested_scopes.issubset(original_scopes):
            raise TokenError("invalid_scope", "Requested scopes exceed authorized scopes.")

        # Revoke old refresh token
        old_hash = _hash_token(refresh_token.token)
        with get_session() as db:
            old_row = db.query(OAuthRefreshToken).filter(
                OAuthRefreshToken.token_hash == old_hash
            ).first()
            if old_row:
                user_id = old_row.user_id
                old_row.is_revoked = True
            else:
                raise TokenError("invalid_grant", "Refresh token not found.")

        # Issue new tokens
        access_token_value = mint_access_token(
            user_id=user_id,
            client_id=client.client_id or "",
            scopes=scopes,
        )

        new_refresh_value = secrets.token_urlsafe(48)
        new_refresh_hash = _hash_token(new_refresh_value)
        refresh_expires = datetime.utcnow() + timedelta(seconds=REFRESH_TOKEN_EXPIRY_SECONDS)

        with get_session() as db:
            db.add(OAuthRefreshToken(
                token_hash=new_refresh_hash,
                client_id=client.client_id or "",
                user_id=user_id,
                scopes=scopes,
                expires_at=refresh_expires,
                is_revoked=False,
            ))

        logger.info("OAuth tokens refreshed: user_id=%d, client_id=%s", user_id, client.client_id)

        return OAuthToken(
            access_token=access_token_value,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_EXPIRY_SECONDS,
            refresh_token=new_refresh_value,
            scope=" ".join(scopes),
        )

    # ---- Revocation ----

    async def revoke_token(
        self, token: AccessToken | RefreshToken
    ) -> None:
        """Revoke a token. Access tokens are JWTs (can't revoke), but
        refresh tokens are revoked in the database."""
        if isinstance(token, RefreshToken):
            token_hash = _hash_token(token.token)
            with get_session() as db:
                row = db.query(OAuthRefreshToken).filter(
                    OAuthRefreshToken.token_hash == token_hash
                ).first()
                if row:
                    row.is_revoked = True
                    logger.info("OAuth refresh token revoked: client_id=%s", token.client_id)
