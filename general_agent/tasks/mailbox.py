"""Inter-agent messaging via file-based mailbox.

Matching cc-haha teammateMailbox pattern.
Each agent has an inbox file in the project's .claude/team/ directory.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field


@dataclass
class MailboxMessage:
    from_name: str = ""
    text: str = ""
    timestamp: float = field(default_factory=time.time)
    read: bool = False


class Mailbox:
    """File-based mailbox for inter-agent messaging."""

    def __init__(self, agent_name: str, team_name: str = "default", project_root: str | None = None):
        self.agent_name = agent_name
        self.team_name = team_name
        self.root = project_root or os.getcwd()
        self.inbox_dir = os.path.join(self.root, ".claude", "team", team_name, "inboxes")

    def _inbox_path(self) -> str:
        return os.path.join(self.inbox_dir, f"{self.agent_name}.json")

    def ensure_dir(self) -> None:
        os.makedirs(self.inbox_dir, exist_ok=True)

    def send(self, to_agent: str, text: str, from_name: str = "") -> None:
        """Send a message to another agent's inbox."""
        self.ensure_dir()
        to_path = os.path.join(self.inbox_dir, f"{to_agent}.json")
        messages = self._read_all(to_path)
        messages.append(MailboxMessage(from_name=from_name or self.agent_name, text=text))
        self._write_all(to_path, messages)

    def receive(self) -> list[MailboxMessage]:
        """Read all messages in own inbox."""
        return self._read_all(self._inbox_path())

    def receive_unread(self) -> list[MailboxMessage]:
        """Read only unread messages."""
        return [m for m in self.receive() if not m.read]

    def mark_read(self) -> None:
        """Mark all messages as read."""
        messages = self._read_all(self._inbox_path())
        for m in messages:
            m.read = True
        self._write_all(self._inbox_path(), messages)

    def drain_unread(self) -> list[str]:
        """Return unread messages as strings and mark them read."""
        msgs = self.receive_unread()
        result = [f"From {m.from_name}: {m.text}" for m in msgs]
        self.mark_read()
        return result

    def _read_all(self, path: str) -> list[MailboxMessage]:
        if not os.path.exists(path):
            return []
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return [MailboxMessage(**m) for m in data]
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_all(self, path: str, messages: list[MailboxMessage]) -> None:
        self.ensure_dir()
        with open(path, "w", encoding="utf-8") as f:
            json.dump([{"from_name": m.from_name, "text": m.text,
                         "timestamp": m.timestamp, "read": m.read}
                        for m in messages], f, ensure_ascii=False, indent=2)
