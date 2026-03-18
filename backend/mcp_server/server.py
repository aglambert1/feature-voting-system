"""
Feature-IQ MCP Server.

Exposes product intelligence data as structured evidence
for Claude Desktop and other MCP clients.

Run: python -m mcp_server.server
"""

from mcp_server import mcp

# Import and register all tool modules
from mcp_server.tools import product  # noqa: E402, F401
from mcp_server.tools import competitive  # noqa: E402, F401
from mcp_server.tools import ideas  # noqa: E402, F401
from mcp_server.tools import synthesis  # noqa: E402, F401
from mcp_server.tools import internal  # noqa: E402, F401
from mcp_server.tools import jobs  # noqa: E402, F401
from mcp_server.tools import composite  # noqa: E402, F401
from mcp_server.tools import evidence  # noqa: E402, F401
from mcp_server import resources  # noqa: E402, F401
from mcp_server import prompts  # noqa: E402, F401

if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
