"""Coordinator mode - orchestrates workers via Agent tool.

Matching cc-haha src/coordinator/coordinatorMode.ts pattern.
The coordinator agent breaks down tasks, spawns worker agents, and synthesizes results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from general_agent.tasks.task import TaskRegistry, TaskState, TaskType
from general_agent.tasks.fork import create_fork_context, run_forked_agent


COORDINATOR_SYSTEM_PROMPT = """You are a coordinator agent. Your job is to:
1. Break down complex tasks into sub-tasks
2. Spawn worker agents using the Agent tool to handle each sub-task
3. Synthesize results from workers into a final answer

## How to use workers
- Use the Agent tool to spawn workers. Each worker runs independently.
- Workers can use all available tools (Bash, Read, Write, Edit, etc.).
- Give workers clear, self-contained prompts with all needed context.
- Workers are synchronous - wait for them to complete before moving on.

## Worker types
- `general-purpose` - For general programming and problem-solving
- `explore` - For exploring and understanding codebases
- `plan` - For planning multi-step tasks before implementation

## Strategy
- Research phase: spawn explore workers in parallel
- Implementation phase: spawn workers for independent file changes
- Verification phase: review results and verify correctness
"""


@dataclass
class CoordinatorState:
    task_registry: TaskRegistry = field(default_factory=TaskRegistry)
    workers_spawned: int = 0
    max_workers: int = 5


async def run_coordinator(
    prompt: str,
    state: Any,
    *,
    max_turns: int = 20,
) -> tuple[str, list[dict[str, Any]]]:
    """Run a coordinator agent that orchestrates workers.

    The coordinator itself uses AgentTool to spawn sub-agents.
    """
    from general_agent.agent.loop import AgentState, run_agent

    coordinator_state = AgentState(
        messages=[{"role": "user", "content": prompt}],
        tool_registry=state.tool_registry,
        max_turns=max_turns,
        system_prompt_extra=COORDINATOR_SYSTEM_PROMPT,
        auto_memory=False,
    )

    return await run_agent(coordinator_state)
