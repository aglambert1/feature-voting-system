"""
Feature-IQ MCP HTTP Server.

HTTP transport entry point for remote MCP clients (Claude Desktop,
Cursor, Claude Code, etc.). Supports OAuth 2.1 (interactive clients)
and API key auth (headless/programmatic) via MultiAuth.

Run: python -m mcp_server.http_server
"""

import logging
from typing import Optional

from jose import jwt, JWTError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from fastmcp.server.auth import MultiAuth

from mcp_server import mcp
from mcp_server.auth import APIKeyAuthProvider
from mcp_server.oauth_provider import FeatureIQOAuthProvider
from mcp_server.oauth_models import OAuthAuthorizationCode
from mcp_server.db import get_session

from app.config import settings

# Import and register all tool modules (same as server.py)
from mcp_server.tools import product  # noqa: F401
from mcp_server.tools import competitive  # noqa: F401
from mcp_server.tools import ideas  # noqa: F401
from mcp_server.tools import synthesis  # noqa: F401
from mcp_server.tools import internal  # noqa: F401
from mcp_server.tools import jobs  # noqa: F401
from mcp_server.tools import composite  # noqa: F401
from mcp_server.tools import evidence  # noqa: F401
from mcp_server import resources  # noqa: F401
from mcp_server import prompts  # noqa: F401

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- OAuth consent endpoint ---
# Served on the MCP server. The frontend redirects here after user approves.

@mcp.custom_route("/oauth/consent", methods=["GET", "POST"])
async def oauth_consent(request: Request) -> Response:
    """Handle OAuth consent flow.

    GET: Return transaction details for the frontend consent page.
    POST: Accept user consent, bind user to auth code, redirect to client.
    """
    if request.method == "GET":
        return await _get_consent_details(request)
    else:
        return await _post_consent_approval(request)


async def _get_consent_details(request: Request) -> Response:
    """Return auth code transaction details for the consent page."""
    txn_id = request.query_params.get("txn_id")
    if not txn_id:
        return JSONResponse({"error": "Missing txn_id"}, status_code=400)

    with get_session() as db:
        row = db.query(OAuthAuthorizationCode).filter(
            OAuthAuthorizationCode.code == txn_id,
            OAuthAuthorizationCode.consumed.is_(False),
        ).first()

        if not row:
            return JSONResponse({"error": "Invalid or expired transaction"}, status_code=404)

        return JSONResponse({
            "txn_id": txn_id,
            "client_id": row.client_id,
            "scopes": row.scopes or [],
        })


async def _post_consent_approval(request: Request) -> Response:
    """Accept consent: bind user to auth code, return redirect URL."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    txn_id = body.get("txn_id")
    user_token = body.get("token")

    if not txn_id or not user_token:
        return JSONResponse({"error": "Missing txn_id or token"}, status_code=400)

    # Verify user's session JWT from the main app
    user_id = _verify_user_jwt(user_token)
    if not user_id:
        return JSONResponse({"error": "Invalid or expired user token"}, status_code=401)

    with get_session() as db:
        row = db.query(OAuthAuthorizationCode).filter(
            OAuthAuthorizationCode.code == txn_id,
            OAuthAuthorizationCode.consumed.is_(False),
        ).first()

        if not row:
            return JSONResponse({"error": "Invalid or expired transaction"}, status_code=404)

        # Bind user to the authorization code
        row.user_id = user_id

        redirect_uri = row.redirect_uri
        state = body.get("state", "")

    # Return redirect URL for the frontend to navigate to
    redirect_url = f"{redirect_uri}?code={txn_id}"
    if state:
        redirect_url += f"&state={state}"

    return JSONResponse({"redirect_url": redirect_url})


def _verify_user_jwt(token: str) -> Optional[int]:
    """Verify a session JWT from the main FastAPI app and return user_id."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        user_id = payload.get("user_id")
        return user_id if isinstance(user_id, int) else None
    except JWTError:
        return None


def main():
    """Start the MCP HTTP server with OAuth + API key authentication."""
    logger.info("Starting Feature-IQ MCP HTTP server")

    mcp_base_url = settings.mcp_base_url
    frontend_url = settings.frontend_url

    oauth_provider = FeatureIQOAuthProvider(
        base_url=mcp_base_url,
        frontend_url=frontend_url,
    )
    api_key_verifier = APIKeyAuthProvider()

    mcp.auth = MultiAuth(
        server=oauth_provider,
        verifiers=[api_key_verifier],
    )

    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001,
        path="/mcp",
        stateless_http=True,
    )


if __name__ == "__main__":
    main()
