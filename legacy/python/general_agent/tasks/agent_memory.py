"""Per-agent memory - each agent type gets its own MEMORY.md.

Matching cc-haha agentMemory.ts pattern.
Stored in .glagent/agent-memory/<agent_type>/ directory.
"""

from __future__ import annotations

import os

from general_agent.memory.store import MemoryStore


def get_agent_memory_store(
    agent_type: str,
    project_root: str | None = None,
) -> MemoryStore:
    """Get a MemoryStore scoped to a specific agent type.

    Directory: <.glagent/agent-memory/<agent_type>/
    Each agent type has independent memories.
    """
    root = project_root or os.getcwd()
    return MemoryStore(root=os.path.join(root, ".glagent", "agent-memory", agent_type))


def inject_agent_memory(
    agent_type: str,
    project_root: str | None = None,
) -> str:
    """Get formatted memory content for injection into agent system prompt."""
    store = get_agent_memory_store(agent_type, project_root)
    return store.format_for_prompt()
