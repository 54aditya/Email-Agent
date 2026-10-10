"""MCP server entry point (stdio transport).

Run directly for testing:   python -m mcp_server.server
Normally it is spawned by agent/mcp_connector.py or by an MCP client such as
Claude Desktop.
"""

import logging
import sys

from mcp.server.fastmcp import FastMCP

from mcp_server.tools import attachment_tools, manage_tools, read_tools, send_tools


logging.basicConfig(stream=sys.stderr, level=logging.INFO)

mcp = FastMCP("email-agent")

for module in (read_tools, send_tools, manage_tools, attachment_tools):
    module.register(mcp)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
