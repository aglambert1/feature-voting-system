"""
Feature-IQ MCP HTTP Server.

HTTP transport entry point for remote MCP clients (Claude Desktop,
Cursor, Claude Code, etc.). Supports OAuth 2.1 (interactive clients)
and API key auth (headless/programmatic) via MultiAuth.

Run: python -m mcp_server.http_server
"""

import logging
from datetime import datetime
from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from fastmcp.server.auth import MultiAuth
from mcp.server.auth.provider import construct_redirect_uri

from mcp_server import mcp
from mcp_server.auth import APIKeyAuthProvider
from mcp_server.oauth_provider import FeatureIQOAuthProvider
from mcp_server.oauth_models import OAuthAuthorizationCode
from mcp_server.db import get_session

from app.config import settings
from app.utils.security import verify_password

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


# --- OAuth login page (served by MCP server) ---

LOGIN_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign in to Feature-IQ</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #f3f4f6; display: flex; align-items: center; justify-content: center;
               min-height: 100vh; }}
        .card {{ background: white; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.1);
                padding: 2.5rem; width: 100%; max-width: 400px; }}
        .icon {{ width: 48px; height: 48px; background: #dbeafe; border-radius: 50%;
                display: flex; align-items: center; justify-content: center; margin: 0 auto 1rem; }}
        .icon svg {{ width: 24px; height: 24px; color: #2563eb; }}
        h1 {{ text-align: center; font-size: 1.5rem; color: #111827; margin-bottom: 0.25rem; }}
        .subtitle {{ text-align: center; color: #6b7280; font-size: 0.875rem; margin-bottom: 1.5rem; }}
        .client-info {{ background: #f9fafb; border-radius: 8px; padding: 0.75rem 1rem;
                       margin-bottom: 1.5rem; }}
        .client-info .label {{ font-size: 0.75rem; color: #6b7280; }}
        .client-info .value {{ font-size: 0.875rem; color: #111827; font-weight: 500; }}
        .field {{ margin-bottom: 1rem; }}
        label {{ display: block; font-size: 0.875rem; font-weight: 500; color: #374151;
                margin-bottom: 0.25rem; }}
        input {{ width: 100%; padding: 0.625rem 0.75rem; border: 1px solid #d1d5db;
                border-radius: 6px; font-size: 0.875rem; }}
        input:focus {{ outline: none; border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }}
        .error {{ background: #fef2f2; color: #dc2626; padding: 0.75rem; border-radius: 6px;
                 font-size: 0.875rem; margin-bottom: 1rem; }}
        button {{ width: 100%; padding: 0.625rem; background: #2563eb; color: white; border: none;
                border-radius: 6px; font-size: 0.875rem; font-weight: 500; cursor: pointer; }}
        button:hover {{ background: #1d4ed8; }}
        .footer {{ text-align: center; font-size: 0.75rem; color: #9ca3af; margin-top: 1rem; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
        </div>
        <h1>Sign in to Feature-IQ</h1>
        <p class="subtitle">Authorize MCP access</p>

        <div class="client-info">
            <div class="label">Application</div>
            <div class="value">{client_name}</div>
        </div>

        {error_html}

        <form method="POST">
            <input type="hidden" name="txn_id" value="{txn_id}" />
            <input type="hidden" name="state" value="{state}" />
            <div class="field">
                <label for="username">Username or email</label>
                <input type="text" id="username" name="username" required autofocus />
            </div>
            <div class="field">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required />
            </div>
            <button type="submit">Sign in &amp; authorize</button>
        </form>

        <p class="footer">This will allow the application to use Feature-IQ tools on your behalf.</p>
    </div>
</body>
</html>"""


def _render_login_page(txn_id: str, client_name: str, state: str, error: str = "") -> str:
    error_html = f'<div class="error">{error}</div>' if error else ""
    return LOGIN_PAGE_HTML.format(
        txn_id=txn_id,
        client_name=client_name,
        state=state,
        error_html=error_html,
    )


@mcp.custom_route("/oauth/login", methods=["GET", "POST"])
async def oauth_login(request: Request) -> Response:
    """OAuth login page served by the MCP server.

    GET: Render login form.
    POST: Validate credentials, bind user to auth code, redirect to client.
    """
    if request.method == "GET":
        txn_id = request.query_params.get("txn_id", "")
        client_name = request.query_params.get("client_name", "MCP Client")
        state = request.query_params.get("state", "")

        if not txn_id:
            return HTMLResponse("<h1>Invalid request — missing transaction ID</h1>", status_code=400)

        return HTMLResponse(_render_login_page(txn_id, client_name, state))

    # POST — handle login
    form = await request.form()
    txn_id = form.get("txn_id", "")
    state = form.get("state", "")
    username = form.get("username", "")
    password = form.get("password", "")
    client_name = request.query_params.get("client_name", "MCP Client")

    if not txn_id or not username or not password:
        return HTMLResponse(
            _render_login_page(txn_id, client_name, state, "Please enter username and password."),
            status_code=400,
        )

    # Validate credentials
    from app.models.user import User
    with get_session() as db:
        user = db.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()

        if not user or not verify_password(password, user.hashed_password):
            return HTMLResponse(
                _render_login_page(txn_id, client_name, state, "Invalid username or password."),
                status_code=401,
            )

        if not user.is_active:
            return HTMLResponse(
                _render_login_page(txn_id, client_name, state, "Account is deactivated."),
                status_code=403,
            )

        user_id = user.id

    # Bind user to auth code and redirect
    with get_session() as db:
        row = db.query(OAuthAuthorizationCode).filter(
            OAuthAuthorizationCode.code == txn_id,
            OAuthAuthorizationCode.consumed.is_(False),
        ).first()

        if not row:
            return HTMLResponse(
                _render_login_page(txn_id, client_name, state, "Session expired. Please try again."),
                status_code=400,
            )

        if row.expires_at < datetime.utcnow():
            return HTMLResponse(
                _render_login_page(txn_id, client_name, state, "Session expired. Please try again."),
                status_code=400,
            )

        row.user_id = user_id
        redirect_uri = row.redirect_uri

    # Redirect to client's callback with auth code
    final_url = construct_redirect_uri(redirect_uri, code=txn_id, state=state or None)
    logger.info("OAuth login: user_id=%d authorized, redirecting to client", user_id)
    return RedirectResponse(url=str(final_url), status_code=302)


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
