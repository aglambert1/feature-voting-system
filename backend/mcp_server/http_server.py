"""
Feature-IQ MCP HTTP Server.

HTTP transport entry point for remote MCP clients (Claude Desktop,
Cursor, Claude Code, etc.). Authenticates via API keys.

Run: python -m mcp_server.http_server
"""

import logging

from mcp_server import mcp
from mcp_server.auth import APIKeyAuthProvider

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


def main():
    """Start the MCP HTTP server with API key authentication."""
    logger.info("Starting Feature-IQ MCP HTTP server")

    # Set auth provider on the shared MCP instance
    mcp.auth = APIKeyAuthProvider()

    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001,
        path="/mcp",
        stateless_http=True,
        show_banner=False,
    )


if __name__ == "__main__":
    main()
