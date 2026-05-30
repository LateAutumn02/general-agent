"""MCPTool — Tool subclass that wraps a remote MCP server tool.

Each MCPTool instance represents one tool from one MCP server.
Naming convention: ``mcp__<server>__<tool>`` to avoid conflicts with built-in tools.

Delegates execution to MCPServerClient.call_tool().
Read-only by default unless the server declares ``readOnlyHint: false``.

Reference: cc-haha src/tools/MCPTool/MCPTool.ts, docs/mcp/flow.md
"""

from __future__ import annotations

import re
from typing import Any

from general_agent.mcp.client import MCPServerClient, MCPToolCallError
from general_agent.mcp.types import MCPToolDef
from general_agent.tools.tool import Tool, ToolResult


# ---------------------------------------------------------------------------
# MCPTool
# ---------------------------------------------------------------------------


class MCPTool(Tool):
    """Represents a remote MCP tool as a local Tool.

    Model sees this as ``mcp__<server>__<tool>``.
    Call path:  agent loop → MCPTool.call() → MCPServerClient.call_tool() → JSON-RPC

    Attributes:
        name:        Fully-qualified name (mcp__server__tool)
        max_result_size_chars: 100KB for MCP results (can be large)
    """

    def __init__(
        self,
        server_name: str,
        tool_def: MCPToolDef,
        client: MCPServerClient,
    ) -> None:
        self._server_name = server_name
        self._tool_def = tool_def
        self._client = client

        # Build qualified name: mcp__<server>__<tool>
        safe_server = self._normalize(server_name)
        safe_tool = self._normalize(tool_def.name)
        self.name = f"mcp__{safe_server}__{safe_tool}"

        # MCP tool results can be large documents / file listings
        self.max_result_size_chars = 100_000

    # ------------------------------------------------------------------
    # Tool metadata
    # ------------------------------------------------------------------

    def get_input_schema(self) -> dict[str, Any]:
        """Return the server-declared JSON Schema for this tool."""
        schema = self._tool_def.inputSchema
        if not schema:
            return {"type": "object", "properties": {}, "required": []}
        return schema

    def is_enabled(self) -> bool:
        """Available only when the parent server is connected."""
        return self._client.is_connected

    def is_read_only(self, args: dict[str, Any]) -> bool:
        """Default True unless the server explicitly marks readOnlyHint=False."""
        return self._tool_def.readOnlyHint

    def is_concurrency_safe(self, args: dict[str, Any]) -> bool:
        """Safe to run in parallel if read-only."""
        return self.is_read_only(args)

    def is_destructive(self, args: dict[str, Any]) -> bool:
        """Destructive if not read-only."""
        return not self._tool_def.readOnlyHint

    async def description(self, input: dict[str, Any] | None = None) -> str:
        return self._tool_def.description or self.name

    async def prompt(self) -> str:
        """Tool description for system prompt injection.

        Caps at 2048 chars to prevent context bloat
        (matching cc-haha's MAX_MCP_DESCRIPTION_LENGTH).
        """
        desc = self._tool_def.description or ""
        max_desc = 2048
        if len(desc) > max_desc:
            desc = desc[:max_desc] + "... [truncated]"
        return desc

    def user_facing_name(self, args: dict[str, Any] | None = None) -> str:
        return f"{self._server_name} - {self._tool_def.name} (MCP)"

    # ------------------------------------------------------------------
    # Core: execution
    # ------------------------------------------------------------------

    async def call(
        self,
        args: dict[str, Any],
        context: Any = None,
        can_use_tool: Any = None,
        on_progress: Any = None,
    ) -> ToolResult:
        """Forward to the MCP server via tools/call."""
        try:
            content_blocks = await self._client.call_tool(
                self._tool_def.name, args
            )
            # Convert content blocks to a text representation
            parts: list[str] = []
            for block in content_blocks:
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                else:
                    # [v1] Non-text content (image, resource) passed as repr
                    parts.append(str(block))

            text = "\n".join(parts) if parts else "(empty result)"
            return ToolResult(data=text)
        except MCPToolCallError as e:
            return ToolResult(data=f"MCP tool error: {e}")
        except Exception as e:
            return ToolResult(data=f"MCP call failed: {e}")

    def map_tool_result_to_block(
        self, output: Any, tool_use_id: str
    ) -> dict[str, Any]:
        """Format tool output as an API-compatible tool_result block."""
        text = str(output)
        is_error = text.startswith("MCP tool error:") or text.startswith("MCP call failed:")
        if len(text) > self.max_result_size_chars:
            text = text[:self.max_result_size_chars] + "\n... (result truncated)"

        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": text,
            "is_error": is_error,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(name: str) -> str:
        """Normalize a server/tool name for use in a qualified identifier.

        Replaces any character not in ``[a-zA-Z0-9_-]`` with an underscore.
        Matches cc-haha's ``normalizeNameForMCP()``.
        """
        return re.sub(r"[^a-zA-Z0-9_-]", "_", name)
