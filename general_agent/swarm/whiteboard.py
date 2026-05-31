"""Agent Whiteboard — structured thinking record readable by other agents.

Reference: ccswarm crates/ccswarm/src/agent/whiteboard.rs
"""

from __future__ import annotations

from general_agent.swarm.types import WhiteboardEntry


class Whiteboard:
    """Per-agent structured thinking record.

    Entries can be marked visible_to specific agent(s) or all (empty list).
    Other agents can read entries via the coordinator.
    """

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self._entries: list[WhiteboardEntry] = []

    def add(self, content: str, entry_type: str = "Note", *,
            related_task: str = "",
            visible_to: list[str] | None = None) -> WhiteboardEntry:
        entry = WhiteboardEntry(
            agent_id=self.agent_id,
            content=content,
            entry_type=entry_type,
            related_task=related_task,
            visible_to=visible_to or [],
        )
        self._entries.append(entry)
        return entry

    def add_discovery(self, content: str, related_task: str = "") -> WhiteboardEntry:
        return self.add(content, "Discovery", related_task=related_task)

    def add_hypothesis(self, content: str, related_task: str = "") -> WhiteboardEntry:
        return self.add(content, "Hypothesis", related_task=related_task)

    def add_decision(self, content: str, related_task: str = "") -> WhiteboardEntry:
        return self.add(content, "Decision", related_task=related_task)

    def add_question(self, content: str, related_task: str = "") -> WhiteboardEntry:
        return self.add(content, "Question", related_task=related_task)

    def add_conclusion(self, content: str, related_task: str = "") -> WhiteboardEntry:
        return self.add(content, "Conclusion", related_task=related_task)

    # ---- query ----

    def get_all(self) -> list[WhiteboardEntry]:
        return list(self._entries)

    def get_visible_to(self, reader_agent_id: str) -> list[WhiteboardEntry]:
        """Return entries visible to a specific agent."""
        return [
            e for e in self._entries
            if not e.visible_to or reader_agent_id in e.visible_to
        ]

    def get_by_type(self, entry_type: str) -> list[WhiteboardEntry]:
        return [e for e in self._entries if e.entry_type == entry_type]

    def get_by_task(self, task_id: str) -> list[WhiteboardEntry]:
        return [e for e in self._entries if e.related_task == task_id]

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"Whiteboard(agent={self.agent_id}, entries={len(self._entries)})"
