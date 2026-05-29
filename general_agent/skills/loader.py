"""Skills loader - scans .claude/skills/ for SKILL.md files.

Matching cc-haha src/skills/loadSkillsDir.ts pattern.
v1: static loading only, inline mode, project-level only.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class SkillDef:
    """A skill definition loaded from SKILL.md."""
    name: str = ""
    description: str = ""
    when_to_use: str = ""
    prompt: str = ""  # Body of SKILL.md (after frontmatter)
    source_path: str = ""
    user_invocable: bool = True  # Can user type /skill-name?


def scan_skills(root: str) -> list[SkillDef]:
    """Scan project .claude/skills/ directory for skill definitions.

    Each skill is a subdirectory containing a SKILL.md file.
    Directory name = skill name.

    Returns:
        List of SkillDef objects, sorted by name.
    """
    skills_dir = os.path.join(root, ".claude", "skills")
    if not os.path.isdir(skills_dir):
        return []

    result = []
    for entry in sorted(os.listdir(skills_dir)):
        skill_path = os.path.join(skills_dir, entry)
        if not os.path.isdir(skill_path):
            continue

        md_path = os.path.join(skill_path, "SKILL.md")
        if not os.path.isfile(md_path):
            continue

        try:
            with open(md_path, encoding="utf-8") as f:
                raw = f.read()
            skill = _parse_skill(raw, entry, md_path)
            if skill.name:
                result.append(skill)
        except Exception:
            pass

    return sorted(result, key=lambda s: s.name)


def _parse_skill(raw: str, dirname: str, path: str) -> SkillDef:
    """Parse SKILL.md file: extract frontmatter and body."""
    skill = SkillDef(name=dirname, source_path=path)
    fm = _FRONTMATTER_RE.match(raw)
    body = raw[fm.end():].strip() if fm else raw.strip()

    if fm:
        for line in fm.group(1).split("\n"):
            if ":" in line:
                key, _, val = line.partition(":")
                key, val = key.strip(), val.strip()
                if key == "name":
                    skill.name = val
                elif key == "description":
                    skill.description = val
                elif key == "when_to_use":
                    skill.when_to_use = val
                elif key == "user-invocable":
                    skill.user_invocable = val.lower() != "false"

    skill.prompt = body
    return skill


def format_skills_for_prompt(skills: list[SkillDef]) -> str:
    """Format skills as a system prompt section."""
    if not skills:
        return ""

    lines = ["\n## Available Skills\n"]
    for skill in skills:
        lines.append(f"### {skill.name}")
        lines.append(f"  {skill.description}")
        if skill.when_to_use:
            lines.append(f"  When to use: {skill.when_to_use}")
        lines.append("")

    lines.append("To invoke a skill, type /<skill-name> in the REPL.")
    lines.append("The skill's instructions will be injected into the conversation.")
    return "\n".join(lines)


def get_slash_commands(skills: list[SkillDef]) -> dict[str, SkillDef]:
    """Get user-invocable skills as slash commands."""
    return {s.name: s for s in skills if s.user_invocable}
