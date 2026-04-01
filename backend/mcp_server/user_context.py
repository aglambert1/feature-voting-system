"""
User context helper for MCP tools.

Extracts the authenticated user_id from the HTTP auth context (set by
FastMCP's AuthContextMiddleware). Falls back to 0 for stdio transport
where no auth context exists.
"""

from mcp.server.auth.middleware.auth_context import auth_context_var


def get_mcp_user_id() -> int:
    """Get authenticated user_id from HTTP auth, or 0 for stdio (local)."""
    ctx = auth_context_var.get(None)
    if ctx and hasattr(ctx, "access_token"):
        return ctx.access_token.claims.get("user_id", 0)
    return 0


def get_mcp_user_label() -> str:
    """Get a label for the MCP user (for created_by fields)."""
    user_id = get_mcp_user_id()
    if user_id:
        return f"mcp_user_{user_id}"
    return "mcp"
