"""Agent definition loader — reads .glagent/agents/<name>/AGENT.md files.

Matches ccswarm agent definition loading pattern.
Each agent is a directory under .glagent/agents/ with an AGENT.md file.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from general_agent.swarm.types import AgentDefinition, AgentPersonality, AgentRole

logger = logging.getLogger("general_agent.swarm.loader")

# Default built-in agents (always available even without AGENT.md files)
BUILTIN_AGENTS: list[AgentDefinition] = [
    AgentDefinition(
        name="frontend",
        role=AgentRole(
            kind="Frontend",
            technologies=["HTML", "CSS", "JavaScript", "TypeScript", "React", "Vue"],
            responsibilities=["UI/UX development", "Client-side logic", "Styling and layout"],
            boundaries=["No backend APIs", "No database schema changes", "No infrastructure"],
        ),
        personality=AgentPersonality(creativity=0.8, formality=0.3),
        system_prompt="You are a frontend specialist. Focus on UI, UX, and client-side code.",
    ),
    AgentDefinition(
        name="backend",
        role=AgentRole(
            kind="Backend",
            technologies=["Python", "FastAPI", "Django", "SQL", "REST", "GraphQL"],
            responsibilities=["API design", "Database management", "Server-side logic", "Authentication"],
            boundaries=["No UI styling", "No frontend framework code", "No CI/CD pipeline"],
        ),
        personality=AgentPersonality(formality=0.6, risk_tolerance=0.2),
        system_prompt="You are a backend specialist. Focus on APIs, databases, and server logic.",
    ),
    AgentDefinition(
        name="devops",
        role=AgentRole(
            kind="DevOps",
            technologies=["Docker", "Kubernetes", "CI/CD", "GitHub Actions", "Terraform"],
            responsibilities=["Deployment pipelines", "Infrastructure as code", "Monitoring", "Scaling"],
            boundaries=["No application logic", "No UI code", "No database schema design"],
        ),
        personality=AgentPersonality(risk_tolerance=0.4, directness=0.9),
        system_prompt="You are a DevOps specialist. Focus on deployment, infrastructure, and CI/CD.",
    ),
    AgentDefinition(
        name="qa",
        role=AgentRole(
            kind="QA",
            technologies=["pytest", "jest", "vitest", "Selenium", "Cypress"],
            responsibilities=["Test automation", "Quality assurance", "Bug reproduction", "Coverage analysis"],
            boundaries=["No feature implementation", "No infrastructure changes", "No production deploys"],
        ),
        personality=AgentPersonality(formality=0.5, directness=0.8),
        system_prompt="You are a QA specialist. Focus on testing, quality, and bug detection.",
    ),
]


def scan_agent_dirs(root: str) -> list[AgentDefinition]:
    """Scan <root>/.glagent/agents/ and ~/.glagent/agents/ for agent definitions.

    Each subdirectory is an agent. AGENT.md contains YAML frontmatter + body.
    If no custom agents found, returns built-in defaults.
    """
    agents: list[AgentDefinition] = []
    seen: set[str] = set()

    # Project-level agents
    _scan_dir(os.path.join(root, ".glagent", "agents"), agents, seen)
    # User-level agents
    _scan_dir(os.path.join(os.path.expanduser("~"), ".glagent", "agents"), agents, seen)

    if not agents:
        logger.info("No custom agents found, using built-in defaults")
        return list(BUILTIN_AGENTS)

    return agents


def _scan_dir(agents_dir: str, agents: list[AgentDefinition], seen: set[str]) -> None:
    if not os.path.isdir(agents_dir):
        return

    for name in sorted(os.listdir(agents_dir)):
        if name in seen:
            continue
        subdir = os.path.join(agents_dir, name)
        if not os.path.isdir(subdir):
            continue

        agent_md = os.path.join(subdir, "AGENT.md")
        if not os.path.isfile(agent_md):
            continue

        try:
            agent_def = _parse_agent_md(agent_md, name)
            if agent_def:
                agents.append(agent_def)
                seen.add(name)
                logger.info("Loaded agent: %s (%s)", name, agent_def.role.kind)
        except Exception as e:
            logger.warning("Failed to parse agent %s: %s", name, e)


def _parse_agent_md(file_path: str, name: str) -> AgentDefinition | None:
    """Parse AGENT.md with optional YAML frontmatter."""
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    frontmatter: dict[str, Any] = {}
    body = content

    # Parse YAML frontmatter if present
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                frontmatter = yaml.safe_load(parts[1]) or {}
            except Exception:
                pass
            body = parts[2].strip()

    # Build role
    role_data = frontmatter.get("role", {})
    role = AgentRole(
        kind=frontmatter.get("kind", role_data.get("kind", "GeneralPurpose")),
        technologies=frontmatter.get("technologies", role_data.get("technologies", [])),
        responsibilities=frontmatter.get("responsibilities", role_data.get("responsibilities", [])),
        boundaries=frontmatter.get("boundaries", role_data.get("boundaries", [])),
    )

    # Build personality
    pers_data = frontmatter.get("personality", {})
    personality = AgentPersonality(
        formality=float(pers_data.get("formality", 0.5)),
        verbosity=float(pers_data.get("verbosity", 0.5)),
        directness=float(pers_data.get("directness", 0.7)),
        creativity=float(pers_data.get("creativity", 0.5)),
        risk_tolerance=float(pers_data.get("risk_tolerance", 0.3)),
    )

    return AgentDefinition(
        name=name,
        role=role,
        personality=personality,
        model=frontmatter.get("model", ""),
        system_prompt=body,
        tools=frontmatter.get("tools", ["all"]),
        auto_accept=frontmatter.get("auto_accept", False),
        risk_threshold=frontmatter.get("risk_threshold", 5),
        max_turns=frontmatter.get("max_turns", 20),
    )
