"""MCP integration for general-agent — public API.

Usage (in REPL or one-shot startup)::

    from general_agent.mcp import init_mcp_servers, shutdown_mcp

    registry = create_registry()
    count = await init_mcp_servers(registry, os.getcwd())
    # ... run agent ...
    await shutdown_mcp()

Reference: cc-haha src/services/mcp/useManageMCPConnections.ts, docs/mcp/flow.md
"""

from __future__ import annotations

import logging

from general_agent.mcp.client import (
    init_all_servers,
    shutdown_all_servers,
    get_connected_servers,
)
from general_agent.mcp.tool import MCPTool
from general_agent.tools.registry import ToolsRegistry

logger = logging.getLogger("general_agent.mcp")


async def init_mcp_servers(registry: ToolsRegistry, cwd: str) -> int:
    """Load MCP config, connect all servers, register discovered tools.

    Called during REPL startup and one-shot mode.

    Args:
        registry: The ToolsRegistry to register MCP tools into.
        cwd:      Working directory to search for .mcp.json.

    Returns:
        Number of successfully-connected MCP servers.
    """
    servers = await init_all_servers(cwd)
    if not servers:
        return 0

    total_tools = 0
    for name, client in servers.items():
        tool_defs = await client.discover_tools()
        for td in tool_defs:
            tool = MCPTool(name, td, client)
            if tool.name:
                registry.register(tool)
                total_tools += 1

        logger.info("MCP '%s': registered %d tools", name, len(tool_defs))

    logger.info("MCP: %d server(s), %d tool(s) registered",
                len(servers), total_tools)
    return len(servers)


async def shutdown_mcp() -> None:
    """Disconnect all MCP servers. Registered with the cleanup system."""
    await shutdown_all_servers()


def get_server_count() -> int:
    """Number of connected MCP servers (for display)."""
    return len(get_connected_servers())


def get_tool_count() -> int:
    """Total tools across all connected MCP servers (for display)."""
    total = 0
    for client in get_connected_servers().values():
        if client.tools:
            total += len(client.tools)
    return total
