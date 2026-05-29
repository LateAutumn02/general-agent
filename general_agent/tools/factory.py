"""Shared tool registry factory - used by both REPL and one-shot modes."""

from general_agent.tools.registry import ToolsRegistry
from general_agent.tools.bash import BashTool
from general_agent.tools.read import FileReadTool
from general_agent.tools.write import FileWriteTool
from general_agent.tools.edit import FileEditTool
from general_agent.tools.grep import GrepTool
from general_agent.tools.glob import GlobTool
from general_agent.tools.webfetch import WebFetchTool
from general_agent.tools.agent_tool import AgentTool


def create_registry() -> ToolsRegistry:
    """Create a registry with all v1 core tools registered."""
    registry = ToolsRegistry()
    registry.register(BashTool())
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(FileEditTool())
    registry.register(GrepTool())
    registry.register(GlobTool())
    registry.register(WebFetchTool())
    registry.register(AgentTool())
    return registry
