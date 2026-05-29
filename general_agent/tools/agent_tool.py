"""AgentTool - spawn sub-agents for parallel work.

Matching cc-haha src/tools/AgentTool/AgentTool.tsx pattern.
The main agent calls this tool to delegate tasks to sub-agents.
"""

from __future__ import annotations

import asyncio
from typing import Any

from general_agent.tools.tool import Tool, ToolResult
from general_agent.tasks.task import TaskRegistry, TaskState, TaskType
from general_agent.tasks.fork import create_fork_context, run_forked_agent


class AgentTool(Tool):
    name = "Agent"

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "A short (3-5 word) description of the task"},
                "prompt": {"type": "string", "description": "The task for the agent to perform"},
                "max_turns": {"type": "integer", "description": "Max API turns (default 20)"},
            },
            "required": ["description", "prompt"],
        }

    def is_read_only(self, args: dict[str, Any]) -> bool:
        return False  # Sub-agent may write files

    def is_concurrency_safe(self, args: dict[str, Any]) -> bool:
        return True  # Can spawn multiple agents

    async def description(self, input: dict[str, Any] | None = None) -> str:
        return input.get("description", "Delegate a task to a sub-agent") if input else "Delegate a task to a sub-agent"

    async def prompt(self) -> str:
        return """Spawn a sub-agent to handle a task independently.

- Use this for: parallel research, independent file operations, background tasks.
- The sub-agent has its own context and can use all tools.
- Results are returned directly when the agent completes.
- Each sub-agent runs synchronously (blocks until done)."""

    async def call(
        self,
        args: dict[str, Any],
        context: Any = None,
        can_use_tool: Any = None,
        on_progress: Any = None,
    ) -> ToolResult:
        prompt = args["prompt"]
        max_turns = args.get("max_turns", 20)

        # Get parent state from context (agent_state passed by loop)
        parent_state = context if context is not None and hasattr(context, "tool_registry") else None

        # Create registry for sub-agent (share parent's or create new)
        registry = parent_state.tool_registry if parent_state else None

        import uuid
        task_id = "b" + uuid.uuid4().hex[:8]
        task = TaskState(
            id=task_id, type=TaskType.LOCAL_AGENT,
            description=args.get("description", ""), prompt=prompt,
        )

        # Create fork context with parent's tool registry
        fork_ctx = create_fork_context(parent_state, agent_id=task_id, max_turns=max_turns)

        # Run fork agent
        result_text, messages = await run_forked_agent(
            fork_ctx, prompt, task=task,
        )

        return ToolResult(data={
            "agent_id": task_id,
            "output": result_text,
            "tool_use_count": task.tool_use_count,
            "status": task.status,
            "messages": messages,
        })

    def map_tool_result_to_block(self, output: Any, tool_use_id: str) -> dict:
        if isinstance(output, dict):
            status = output.get("status", "completed")
            text = output.get("output", "")
            if len(text) > 5000:
                text = text[:4997] + "..."
            return {"type": "tool_result", "tool_use_id": tool_use_id,
                    "content": text, "is_error": status == "failed"}
        return {"type": "tool_result", "tool_use_id": tool_use_id,
                "content": str(output)[:5000], "is_error": False}
