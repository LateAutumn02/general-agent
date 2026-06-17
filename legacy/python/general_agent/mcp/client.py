"""MCP protocol client — ~~initialize, discover tools, call tools~~.

MCPServerClient wraps an MCPServerProcess to add MCP protocol semantics:
  - Full handshake (initialize → notifications/initialized)
  - Tool discovery with caching
  - Transparent reconnect on disconnect
  - Concurrent-safe connection management

Module-level API:
  - init_all_servers()  → connect & discover for all configured servers
  - shutdown_all_servers() → cleanup all connections

Reference: cc-haha src/services/mcp/client.ts, docs/mcp/flow.md
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from general_agent.mcp.config import get_mcp_servers
from general_agent.mcp.transport import (
    MCPServerProcess,
    MCPTransportError,
    ServerDisconnectedError,
)
from general_agent.mcp.types import MCPServerConfig, MCPToolDef

logger = logging.getLogger("general_agent.mcp.client")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MCP_PROTOCOL_VERSION = "2024-11-05"
CLIENT_NAME = "general-agent"
CLIENT_VERSION = "0.1.0"

# Per-process server registry (module-level singleton)
_servers: dict[str, "MCPServerClient"] = {}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MCPToolCallError(Exception):
    """Raised when a MCP tools/call returns isError: true."""


# ---------------------------------------------------------------------------
# MCPServerClient
# ---------------------------------------------------------------------------


class MCPServerClient:
    """Manages the full lifecycle of one MCP server.

    Wraps MCPServerProcess and adds protocol marshalling:
      - connect():       spawn + MCP handshake
      - discover_tools(): tools/list → list[MCPToolDef]
      - call_tool():     tools/call → content blocks

    On disconnect, automatically reconnects and retries once.
    """

    def __init__(self, name: str, config: MCPServerConfig) -> None:
        self.name = name
        self.config = config
        self._transport: MCPServerProcess | None = None
        self._tools: list[MCPToolDef] | None = None
        self._lock = asyncio.Lock()

    # --- properties ---

    @property
    def is_connected(self) -> bool:
        return self._transport is not None and self._transport.is_connected

    @property
    def tools(self) -> list[MCPToolDef]:
        """Cached tool definitions (empty if not yet discovered)."""
        return list(self._tools) if self._tools else []

    # --- lifecycle ---

    async def connect(self) -> None:
        """Spawn process and perform MCP handshake.

        Steps:
          1. Start the transport (spawn subprocess)
          2. Send initialize request
          3. Send notifications/initialized (no response expected)

        Idempotent — does nothing if already connected.
        Thread-safe via internal asyncio.Lock.
        """
        async with self._lock:
            if self.is_connected:
                return

            # Clean up any stale transport
            if self._transport:
                await self._transport.close()
                self._transport = None

            transport = MCPServerProcess(self.name, self.config)
            await transport.start()

            try:
                # Step 1: initialize
                init_result = await transport.send_request("initialize", {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {
                        "name": CLIENT_NAME,
                        "version": CLIENT_VERSION,
                    },
                })

                # Step 2: notifications/initialized
                await transport.send_notification("notifications/initialized")

                self._transport = transport
                logger.info(
                    "MCP server '%s' connected (protocol: %s)",
                    self.name,
                    init_result.get("protocolVersion", "unknown"),
                )
            except Exception:
                await transport.close()
                raise

    async def discover_tools(self) -> list[MCPToolDef]:
        """Fetch tool definitions from the server via tools/list.

        Results are cached on first call. To force re-discovery,
        clear ``self._tools`` manually after a reconnect.
        """
        await self._ensure_connected()

        if self._tools is not None:
            return list(self._tools)

        assert self._transport is not None
        result = await self._transport.send_request("tools/list")
        raw_tools: list[dict[str, Any]] = result.get("tools", [])

        tools: list[MCPToolDef] = []
        for t in raw_tools:
            annotations: dict[str, Any] = t.get("annotations", {}) or {}
            tools.append(MCPToolDef(
                name=t.get("name", ""),
                description=t.get("description", ""),
                inputSchema=t.get("inputSchema", {"type": "object", "properties": {}}),
                readOnlyHint=annotations.get("readOnlyHint", True),
            ))

        self._tools = tools
        logger.debug("MCP '%s': discovered %d tools", self.name, len(tools))
        return list(tools)

    async def call_tool(
        self, tool_name: str, args: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Invoke a tool on the MCP server via tools/call.

        On disconnect, reconnects and retries once (transparent to caller).

        Returns:
            The content array from the response (list of dicts with "type", "text", etc.)

        Raises:
            MCPToolCallError: if the server returns isError: true.
            MCPTransportError: if the connection is lost and reconnect fails.
        """
        await self._ensure_connected()

        try:
            assert self._transport is not None
            result = await self._transport.send_request("tools/call", {
                "name": tool_name,
                "arguments": args,
            })
        except ServerDisconnectedError:
            logger.info("MCP '%s': disconnected during tool call, reconnecting...",
                        self.name)
            await self._reconnect()
            assert self._transport is not None
            result = await self._transport.send_request("tools/call", {
                "name": tool_name,
                "arguments": args,
            })

        content: list[dict[str, Any]] = result.get("content", [])
        is_error: bool = result.get("isError", False)

        if is_error:
            error_parts: list[str] = []
            for c in content:
                if c.get("type") == "text":
                    error_parts.append(c.get("text", ""))
            error_msg = "; ".join(error_parts) or "MCP tool returned error"
            raise MCPToolCallError(error_msg)

        return content

    async def disconnect(self) -> None:
        """Close the server connection and release resources."""
        if self._transport:
            await self._transport.close()
            self._transport = None
        self._tools = None

    # --- internals ---

    async def _ensure_connected(self) -> None:
        """Connect if not already connected."""
        if not self.is_connected:
            await self.connect()

    async def _reconnect(self) -> None:
        """Close stale transport, reconnect, and rediscover tools."""
        if self._transport:
            await self._transport.close()
            self._transport = None
        self._tools = None
        await self.connect()
        await self.discover_tools()


# ---------------------------------------------------------------------------
# Module-level API
# ---------------------------------------------------------------------------


async def init_all_servers(cwd: str) -> dict[str, MCPServerClient]:
    """Load MCP config, connect all servers, discover their tools.

    Returns:
        Dict of server name → MCPServerClient for servers that connected successfully.

    Failed servers are logged but do not block other servers from connecting.
    """
    configs = get_mcp_servers(cwd)
    if not configs:
        return {}

    async def _connect_one(name: str, cfg: MCPServerConfig) -> None:
        client = MCPServerClient(name, cfg)
        try:
            await client.connect()
            await client.discover_tools()
            _servers[name] = client
        except Exception as e:
            logger.warning("MCP server '%s' connection failed: %s", name, e)
            # [v1] No retry queue — user can restart or edit config

    tasks = [
        asyncio.create_task(_connect_one(name, cfg))
        for name, cfg in configs.items()
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

    return dict(_servers)


async def shutdown_all_servers() -> None:
    """Disconnect all MCP servers. Idempotent — safe to call multiple times."""
    for name, client in list(_servers.items()):
        try:
            await client.disconnect()
        except Exception:
            logger.exception("MCP server '%s' disconnect failed", name)
    _servers.clear()


def get_connected_servers() -> dict[str, MCPServerClient]:
    """Return a snapshot of currently-connected servers."""
    return dict(_servers)
