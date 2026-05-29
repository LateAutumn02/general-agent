"""Fork agent - runs sub-agents with isolated context, sharing parent prompt cache.

createSubagentContext: clones parent ToolUseContext, isolating mutable state.
runForkedAgent: executes a query loop in a sub-agent, returning results.

Reference: cc-haha src/utils/forkedAgent.ts, src/tools/AgentTool/runAgent.ts
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from general_agent.tasks.task import TaskRegistry, TaskState, TaskStatus

logger = logging.getLogger("general_agent.tasks")


@dataclass
class ForkContext:
    """Isolated context for a forked sub-agent (matching cc-haha createSubagentContext)."""

    agent_id: str = ""
    tool_registry: Any = None  # Cloned from parent
    abort_signal: asyncio.Event = field(default_factory=asyncio.Event)
    max_turns: int = 20
    parent_messages: list[dict[str, Any]] = field(default_factory=list)


def create_fork_context(
    parent_state: Any,
    agent_id: str = "",
    max_turns: int = 20,
) -> ForkContext:
    """Create isolated context for a forked sub-agent.

    Matching cc-haha createSubagentContext pattern:
    - Clone tool registry from parent (tools shared)
    - Fresh abort signal (linked to parent for cascading)
    - Isolated message space
    """
    return ForkContext(
        agent_id=agent_id,
        tool_registry=parent_state.tool_registry if parent_state else _new_registry(),
        max_turns=max_turns,
        parent_messages=list(getattr(parent_state, "messages", [])) if parent_state else [],
    )


def _new_registry():
    """Create a new tool registry when parent state is unavailable."""
    from general_agent.tools.registry import ToolsRegistry
    from general_agent.tools.bash import BashTool
    from general_agent.tools.read import FileReadTool
    from general_agent.tools.write import FileWriteTool
    from general_agent.tools.edit import FileEditTool
    from general_agent.tools.grep import GrepTool
    registry = ToolsRegistry()
    registry.register(BashTool())
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(FileEditTool())
    registry.register(GrepTool())
    return registry


async def run_forked_agent(
    ctx: ForkContext,
    prompt: str,
    *,
    task: TaskState | None = None,
    task_registry: TaskRegistry | None = None,
    system_prompt_extra: str = "",
) -> tuple[str, list[dict[str, Any]]]:
    """Run a forked sub-agent with its own query loop.

    Matches cc-haha runForkedAgent pattern:
    1. Create isolated context
    2. Build initial messages (child prompt only)
    3. Run query loop (same as main agent)
    4. Clean up and return result

    Args:
        ctx: Isolated fork context.
        prompt: The task prompt for the sub-agent.
        task: Optional task state for progress tracking.
        task_registry: Optional registry for task lifecycle.

    Returns:
        (output_text, all_messages)
    """
    from general_agent.agent.loop import AgentState, run_agent
    from general_agent.agent.prompt import build_system_prompt

    # Create child AgentState with prompt
    # Prepend parent conversation so fork can see context (cc-haha CacheSafeParams)
    child_messages = list(ctx.parent_messages) + [{"role": "user", "content": prompt}]
    child_state = AgentState(
        messages=child_messages,
        tool_registry=ctx.tool_registry,
        max_turns=ctx.max_turns,
        abort_signal=ctx.abort_signal,
        auto_memory=False,
        is_fork_agent=True,
        system_prompt_extra=system_prompt_extra,
    )

    if task:
        task.status = TaskStatus.RUNNING

    try:
        result_text, messages = await run_agent(child_state)

        if task_registry and task:
            task_registry.complete(task.id, result=result_text)
        return result_text, messages

    except Exception as e:
        logger.error("Fork agent %s failed: %s", ctx.agent_id, e)
        if task_registry and task:
            task_registry.complete(task.id, error=str(e))
        raise
