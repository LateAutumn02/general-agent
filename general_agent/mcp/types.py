"""MCP type definitions — ~~MCPServerConfig, MCPToolDef, MCPServerState~~.

v1 scope: stdio transport only. No SSE/HTTP/WS/OAuth types yet.

Reference: cc-haha src/services/mcp/types.ts, docs/mcp/data-structure.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP stdio server. Maps to a .mcp.json entry.

    Fields:
        command: Executable to spawn (e.g. "npx", "python")
        args:    Command-line arguments
        env:     Extra environment variables merged with parent env
    """
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class MCPToolDef:
    """MCP tool definition returned by tools/list.

    Fields:
        name:         Original tool name from the server
        description:  Human-readable description (capped to 2048 chars when rendering)
        inputSchema:  JSON Schema for tool parameters
        readOnlyHint: From annotations.readOnlyHint; defaults to True (v1 safe default)
    """
    name: str = ""
    description: str = ""
    inputSchema: dict[str, Any] = field(default_factory=dict)
    readOnlyHint: bool = True
