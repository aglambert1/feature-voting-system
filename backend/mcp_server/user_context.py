"""
User context helper for MCP tools.

Extracts the authenticated user_id from the HTTP auth context (set by
FastMCP's AuthContextMiddleware). Falls back to 0 for stdio transport
where no auth context exists.

The MCP AccessToken pydantic model doesn't carry custom claims, so we
decode user_id from the JWT token string directly.
"""

from mcp.server.auth.middleware.auth_context import auth_context_var


def get_mcp_user_id() -> int:
    """Get authenticated user_id from HTTP auth, or 0 for stdio (local)."""
    ctx = auth_context_var.get(None)
    if ctx and hasattr(ctx, "access_token") and ctx.access_token:
        token = ctx.access_token
        # Decode user_id from the JWT — AccessToken doesn't carry custom claims
        if hasattr(token, "token") and token.token:
            from mcp_server.oauth_jwt import verify_access_token_claims
            return verify_access_token_claims(token.token).get("user_id", 0)
    return 0


def get_mcp_user_label() -> str:
    """Get a label for the MCP user (for created_by fields)."""
    user_id = get_mcp_user_id()
    if user_id:
        return f"mcp_user_{user_id}"
    return "mcp"
