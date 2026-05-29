"""Team management - team directory structure and member tracking.

Matching cc-haha src/utils/team/ patterns.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class TeamMember:
    name: str = ""
    agent_type: str = "general-purpose"
    status: str = "idle"  # idle / working / completed
    task_id: str | None = None


class TeamManager:
    """Manages team directory and member state."""

    def __init__(self, team_name: str = "default", project_root: str | None = None):
        self.team_name = team_name
        self.root = project_root or os.getcwd()
        self.team_dir = os.path.join(self.root, ".claude", "team", team_name)

    def ensure_dir(self) -> None:
        os.makedirs(self.team_dir, exist_ok=True)
        os.makedirs(os.path.join(self.team_dir, "inboxes"), exist_ok=True)
        os.makedirs(os.path.join(self.team_dir, "transcripts"), exist_ok=True)

    def add_member(self, name: str, agent_type: str = "general-purpose") -> TeamMember:
        """Register a new team member."""
        self.ensure_dir()
        member = TeamMember(name=name, agent_type=agent_type)
        self._save_member(member)
        return member

    def remove_member(self, name: str) -> bool:
        """Remove a team member."""
        path = self._member_path(name)
        try:
            os.unlink(path)
            return True
        except FileNotFoundError:
            return False

    def list_members(self) -> list[TeamMember]:
        """List all team members."""
        self.ensure_dir()
        members_dir = os.path.join(self.team_dir, "members")
        os.makedirs(members_dir, exist_ok=True)
        result = []
        for fname in sorted(os.listdir(members_dir)):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(members_dir, fname), encoding="utf-8") as f:
                    data = json.load(f)
                result.append(TeamMember(**data))
            except Exception:
                pass
        return result

    def update_member(self, name: str, **kwargs) -> None:
        """Update member state."""
        path = self._member_path(name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            data.update(kwargs)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f)

    def _member_path(self, name: str) -> str:
        members_dir = os.path.join(self.team_dir, "members")
        os.makedirs(members_dir, exist_ok=True)
        return os.path.join(members_dir, f"{name}.json")

    def _save_member(self, member: TeamMember) -> None:
        os.makedirs(os.path.join(self.team_dir, "members"), exist_ok=True)
        path = self._member_path(member.name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"name": member.name, "agent_type": member.agent_type,
                         "status": member.status, "task_id": member.task_id}, f)
