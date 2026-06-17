"""Tool registry - manages tool registration and lookup.

Maps to cc-haha's tool pool (assembled in AppState).
"""

from __future__ import annotations

from general_agent.tools.tool import Tool


class ToolsRegistry:
    """Manages all registered tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool by name."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def get_enabled(self) -> list[Tool]:
        """Return all tools that are currently enabled."""
        return [t for t in self._tools.values() if t.is_enabled()]

    def filter(self, fn) -> list[Tool]:
        """Filter tools by predicate."""
        return [t for t in self._tools.values() if fn(t)]

    def all(self) -> list[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# Shared registry instance
registry = ToolsRegistry()
