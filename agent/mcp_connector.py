"""Starts the MCP server as a subprocess and talks to it over stdio."""

import os
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config.settings import BASE_DIR


class MCPConnector:
    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self.session: ClientSession | None = None

    async def __aenter__(self) -> "MCPConnector":
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server.server"],
            cwd=str(BASE_DIR),
            env=dict(os.environ),
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stack.aclose()

    async def get_anthropic_tools(self) -> list[dict]:
        """Convert MCP tool definitions to the Anthropic tool-use format."""
        result = await self.session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict) -> tuple[str, bool]:
        """Returns (text, is_error)."""
        result = await self.session.call_tool(name, arguments)
        text = "\n".join(
            block.text
            for block in result.content
            if getattr(block, "type", "") == "text"
        )
        return text, bool(result.isError)
