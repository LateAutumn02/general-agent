"""Tool base class - matching cc-haha src/Tool.ts buildTool() pattern.

Provides fail-safe defaults for all tool methods.
Subclasses override only what they need.

Reference: cc-haha src/Tool.ts:362-792, docs/tools/data-structure.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class PermissionResult:
    """Permission check result. Maps to cc-haha PermissionResult."""
    behavior: str = "allow"  # "allow" | "deny" | "ask" | "passthrough"
    updated_input: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    decision_reason: dict[str, Any] | None = None


@dataclass
class ToolResult:
    """Tool execution result. Maps to cc-haha ToolResult<T>."""
    data: Any = ""
    new_messages: list[Any] = field(default_factory=list)
    context_modifier: Callable | None = None


# ---------------------------------------------------------------------------
# Tool base class
# ---------------------------------------------------------------------------


class Tool:
    """Base class for all tools. Provides cc-haha buildTool() defaults.

    Usage: subclass and override only the methods you need.
        class BashTool(Tool):
            name = "Bash"
            is_read_only = lambda self, i: False
            async def call(self, args, context): ...
    """

    # --- Identification (must override) ---
    name: str = ""             # Unique tool name
    aliases: list[str] = []    # Alternative names (backward compat)
    max_result_size_chars: int = 30_000  # Output over this goes to disk

    # --- Input/output ---
    def get_input_schema(self) -> dict[str, Any]:
        """JSON Schema for tool input parameters."""
        return {"type": "object", "properties": {}, "required": []}

    def get_output_schema(self) -> dict[str, Any]:
        """JSON Schema for tool output."""
        return {}

    # --- Core methods ---
    async def call(
        self,
        args: dict[str, Any],
        context: Any = None,
        can_use_tool: Callable | None = None,
        on_progress: Callable | None = None,
    ) -> ToolResult:
        """Execute the tool. Subclasses MUST override this."""
        raise NotImplementedError(f"{self.name}.call() not implemented")

    async def description(self, input: dict[str, Any] | None = None) -> str:
        """One-line description for the model."""
        return self.name

    async def prompt(self) -> str:
        """Full prompt text explaining how to use the tool."""
        return ""

    async def validate_input(
        self, args: dict[str, Any], context: Any = None
    ) -> dict | None:
        """Pre-flight validation. Return error dict if invalid, None if ok."""
        return None

    def map_tool_result_to_block(
        self, output: Any, tool_use_id: str
    ) -> dict[str, Any]:
        """Format tool output as an API-compatible tool_result block."""
        content = str(output)
        if self.max_result_size_chars and len(content) > self.max_result_size_chars:
            content = content[:self.max_result_size_chars] + "\n... (truncated)"
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": content,
            "is_error": False,
        }

    # --- Properties ---
    def is_enabled(self) -> bool:
        """Whether this tool is available right now."""
        return True

    def is_read_only(self, args: dict[str, Any]) -> bool:
        """Whether this call only reads (never writes)."""
        return False

    def is_concurrency_safe(self, args: dict[str, Any]) -> bool:
        """Whether this tool can run in parallel with other calls."""
        return False

    def is_destructive(self, args: dict[str, Any]) -> bool:
        """Whether this operation is irreversible."""
        return False

    def user_facing_name(self, args: dict[str, Any] | None = None) -> str:
        """Display name in the UI."""
        return self.name

    # --- Permissions ---
    async def check_permissions(
        self, args: dict[str, Any], context: Any = None
    ) -> PermissionResult:
        """Tool-specific permission check. Default: allow everything."""
        return PermissionResult(behavior="allow", updated_input=args)

    def to_classifier_input(self, args: dict[str, Any]) -> str:
        """Input for security classifier. Empty = skip."""
        return ""

    # --- Helpers ---
    def get_path(self, args: dict[str, Any]) -> str | None:
        """Extract the file path from tool arguments (if this tool touches files)."""
        return args.get("file_path") or args.get("command")

    def get_activity_description(self, args: dict[str, Any]) -> str:
        """What this tool is doing (for progress display)."""
        return self.name


# ---------------------------------------------------------------------------
# Factory (matching cc-haha buildTool pattern)
# ---------------------------------------------------------------------------


def build_tool(cls: type[Tool], **overrides) -> Tool:
    """Factory that creates a Tool instance with overrides.

    Equivalent to cc-haha's buildTool() spread pattern:
        {DEFAULTS, userFacingName: name, ...userOverrides}
    """
    instance = cls()
    instance.name = overrides.pop("name", instance.name)

    for attr, value in overrides.items():
        setattr(instance, attr, value)

    return instance
