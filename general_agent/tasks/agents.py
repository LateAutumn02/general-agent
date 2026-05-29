"""Agent definitions - load from .claude/agents/ directory.

Matching cc-haha src/tools/AgentTool/loadAgentsDir.ts pattern.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class AgentDefinition:
    """An agent type definition loaded from a markdown file."""

    agent_type: str = ""         # Unique name (GeneralPurpose, Explore, etc.)
    when_to_use: str = ""        # When the LLM should select this agent
    tools: list[str] = field(default_factory=lambda: ["*"])  # Tool allowlist
    disallowed_tools: list[str] = field(default_factory=list)
    model: str = "inherit"
    max_turns: int = 20
    background: bool = False
    initial_prompt: str = ""     # Injected before first user turn
    omit_memory: bool = False    # Skip memory injection
    get_system_prompt: str = ""  # Custom system prompt text
    source: str = "project"      # "built-in" | "project" | "plugin"

    @classmethod
    def from_markdown(cls, raw: str, source_path: str = "") -> AgentDefinition:
        """Parse a markdown agent definition file."""
        fm = _FRONTMATTER_RE.match(raw)
        body = raw[fm.end():].strip() if fm else ""

        defn = cls(source=source_path)
        if fm:
            for line in fm.group(1).split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    key, val = key.strip(), val.strip()
                    if key == "name":
                        defn.agent_type = val
                    elif key == "when_to_use":
                        defn.when_to_use = val
                    elif key == "tools":
                        defn.tools = [t.strip() for t in val.split(",")]
                    elif key == "disallowed_tools":
                        defn.disallowed_tools = [t.strip() for t in val.split(",")]
                    elif key == "model":
                        defn.model = val
                    elif key == "max_turns":
                        defn.max_turns = int(val)
                    elif key == "background":
                        defn.background = val.lower() == "true"

        defn.get_system_prompt = body
        if not defn.agent_type:
            defn.agent_type = os.path.splitext(os.path.basename(source_path))[0]
        return defn


# Built-in agents (matching cc-haha builtInAgents.ts)
BUILTIN_AGENTS = [
    AgentDefinition(
        agent_type="general-purpose",
        when_to_use="For general programming and problem-solving tasks",
        source="built-in",
        get_system_prompt="You are a helpful general-purpose AI assistant.",
    ),
    AgentDefinition(
        agent_type="explore",
        when_to_use="For exploring and understanding codebases",
        tools=["*"],
        max_turns=10,
        source="built-in",
        get_system_prompt="You are a code explorer. Read files, search for patterns, and report findings concisely.",
    ),
    AgentDefinition(
        agent_type="plan",
        when_to_use="For planning multi-step tasks before implementation",
        tools=["Read", "Glob", "Grep"],
        max_turns=5,
        source="built-in",
        get_system_prompt="You are a planning agent. Review the codebase and create a detailed implementation plan.",
    ),
]


def load_project_agents(root: str) -> dict[str, AgentDefinition]:
    """Scan .claude/agents/ directory for custom agent definitions."""
    agents_dir = os.path.join(root, ".claude", "agents")
    if not os.path.isdir(agents_dir):
        return {}

    result = {}
    for fname in os.listdir(agents_dir):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(agents_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                raw = f.read()
            defn = AgentDefinition.from_markdown(raw, fpath)
            result[defn.agent_type] = defn
        except Exception:
            pass
    return result


def get_available_agents(root: str) -> dict[str, AgentDefinition]:
    """Get all available agents: built-in + project-specific."""
    agents = {a.agent_type: a for a in BUILTIN_AGENTS}
    project = load_project_agents(root)
    agents.update(project)  # Project overrides built-in
    return agents
