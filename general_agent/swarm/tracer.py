"""Activity tracer — records and displays what each agent does in real-time.

Every agent action is recorded: task start/end, messages sent/received,
whiteboard updates, quality reviews.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from general_agent.swarm.types import AgentMessage, MessageType, TaskResult, WhiteboardEntry


@dataclass
class TraceEvent:
    """A single observable event in the swarm."""
    timestamp: float = field(default_factory=time.monotonic)
    event_type: str = ""          # task_start|task_end|msg_sent|msg_received|wb_write
                                  # |delegation|quality|agent_create|agent_error
    agent_id: str = ""
    agent_role: str = ""
    task_id: str = ""
    description: str = ""         # human-readable summary
    detail: Any = None            # optional structured detail

    def format(self) -> str:
        """Return a single-line display string."""
        role_tag = f"[{self.agent_role}]" if self.agent_role else ""
        short_id = self.agent_id[:8] if self.agent_id else ""
        tag = f"  {short_id} {role_tag}" if (short_id or role_tag) else "  ·"

        if self.event_type == "task_start":
            return f"{tag} \033[33m▶\033[0m {self.description}"
        if self.event_type == "task_end":
            dur = ""
            if isinstance(self.detail, dict) and "duration_ms" in self.detail:
                dur = f" \033[2m({self.detail['duration_ms']}ms)\033[0m"
            return f"{tag} \033[32m✓\033[0m {self.description}{dur}"
        if self.event_type == "msg_sent":
            return f"{tag} \033[2m→\033[0m {self.description}"
        if self.event_type == "msg_received":
            return f"{tag} \033[2m←\033[0m {self.description}"
        if self.event_type == "wb_write":
            return f"{tag} \033[2m📝\033[0m {self.description}"
        if self.event_type == "delegation":
            return f"{tag} \033[36m◆\033[0m {self.description}"
        if self.event_type == "quality":
            return f"{tag} \033[35m★\033[0m {self.description}"
        if self.event_type == "agent_create":
            return f"  \033[2m+\033[0m {self.description}"
        if self.event_type == "agent_error":
            return f"{tag} \033[31m✗\033[0m {self.description}"
        return f"{tag} {self.description}"


class SwarmTracer:
    """Records all swarm activity for display and debugging.

    Callbacks can be registered to react to events in real-time.
    """

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []
        self._listeners: list[Callable[[TraceEvent], None]] = []

    def on_event(self, listener: Callable[[TraceEvent], None]) -> None:
        """Register a real-time event listener."""
        self._listeners.append(listener)

    def emit(self, **kwargs: Any) -> TraceEvent:
        """Record and broadcast an event."""
        event = TraceEvent(**kwargs)
        self._events.append(event)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass
        return event

    # ---- convenience methods ----

    def task_start(self, agent_id: str, role: str, task_id: str, description: str) -> TraceEvent:
        return self.emit(
            event_type="task_start",
            agent_id=agent_id, agent_role=role, task_id=task_id,
            description=description,
        )

    def task_end(self, agent_id: str, role: str, task_id: str, result: TaskResult) -> TraceEvent:
        return self.emit(
            event_type="task_end",
            agent_id=agent_id, agent_role=role, task_id=task_id,
            description=result.output[:120] if result.output else f"status={result.status.value}",
            detail={"duration_ms": result.duration_ms, "status": result.status.value},
        )

    def msg_sent(self, msg: AgentMessage, sender_role: str = "") -> TraceEvent:
        target = msg.recipient_id[:8] if msg.recipient_id else "all"
        return self.emit(
            event_type="msg_sent",
            agent_id=msg.sender_id, agent_role=sender_role,
            description=f"→ {target}: {_msg_summary(msg)}",
            detail=msg,
        )

    def msg_received(self, msg: AgentMessage, receiver_role: str = "") -> TraceEvent:
        return self.emit(
            event_type="msg_received",
            agent_id=msg.recipient_id, agent_role=receiver_role,
            description=f"← {msg.sender_id[:8]}: {_msg_summary(msg)}",
            detail=msg,
        )

    def wb_write(self, agent_id: str, role: str, entry: WhiteboardEntry) -> TraceEvent:
        return self.emit(
            event_type="wb_write",
            agent_id=agent_id, agent_role=role,
            description=f"{entry.entry_type}: {entry.content[:80]}",
            detail=entry,
        )

    def delegation(self, task_id: str, target_role: str, source: str, confidence: float) -> TraceEvent:
        return self.emit(
            event_type="delegation",
            task_id=task_id, agent_role=target_role,
            description=f"Routing task → {target_role} ({source}, {confidence:.0%})",
        )

    def quality(self, task_id: str, score: float, suggestions: list[str]) -> TraceEvent:
        return self.emit(
            event_type="quality",
            task_id=task_id,
            description=f"Score {score:.2f}" + (f" ({len(suggestions)} suggestions)" if suggestions else ""),
            detail={"score": score, "suggestions": suggestions},
        )

    def agent_create(self, agent_id: str, role: str) -> TraceEvent:
        return self.emit(
            event_type="agent_create",
            agent_id=agent_id, agent_role=role,
            description=f"Created {role} agent ({agent_id[:8]})",
        )

    def agent_error(self, agent_id: str, role: str, error: str) -> TraceEvent:
        return self.emit(
            event_type="agent_error",
            agent_id=agent_id, agent_role=role,
            description=error,
        )

    # ---- query ----

    def recent(self, n: int = 20) -> list[TraceEvent]:
        return self._events[-n:]

    def by_agent(self, agent_id: str) -> list[TraceEvent]:
        return [e for e in self._events if e.agent_id == agent_id]

    def communications(self) -> list[TraceEvent]:
        """Only msg_sent / msg_received events."""
        return [e for e in self._events if e.event_type in ("msg_sent", "msg_received")]

    def clear(self) -> None:
        self._events.clear()

    # ---- persistence ----

    def to_dict(self) -> dict[str, Any]:
        """Serialize all events to a dict for JSON storage."""
        return {
            "events": [
                {
                    "timestamp": e.timestamp,
                    "event_type": e.event_type,
                    "agent_id": e.agent_id,
                    "agent_role": e.agent_role,
                    "task_id": e.task_id,
                    "description": e.description,
                    "detail": self._serialize_detail(e.detail),
                }
                for e in self._events
            ]
        }

    @staticmethod
    def _serialize_detail(detail: Any) -> Any:
        if detail is None:
            return None
        if isinstance(detail, dict):
            return detail
        if hasattr(detail, "__dict__"):
            return {
                k: v for k, v in detail.__dict__.items()
                if isinstance(v, (str, int, float, bool, list, dict, type(None)))
            }
        return str(detail)[:500]

    def save_to_file(self, file_path: str) -> None:
        """Persist full trace to a JSON file."""
        import json
        import os
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            import logging
            logging.getLogger("general_agent.swarm").warning(
                "Failed to save swarm trace: %s", e
            )

    def load_from_file(self, file_path: str) -> list[TraceEvent]:
        """Load trace events from a JSON file."""
        import json
        import os
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            events = []
            for e in data.get("events", []):
                events.append(TraceEvent(
                    timestamp=e.get("timestamp", 0),
                    event_type=e.get("event_type", ""),
                    agent_id=e.get("agent_id", ""),
                    agent_role=e.get("agent_role", ""),
                    task_id=e.get("task_id", ""),
                    description=e.get("description", ""),
                    detail=e.get("detail"),
                ))
            self._events = events
            return events
        except Exception as e:
            import logging
            logging.getLogger("general_agent.swarm").warning(
                "Failed to load swarm trace: %s", e
            )
            return []


def _msg_summary(msg: AgentMessage) -> str:
    """Short summary of a message for display."""
    mt = msg.msg_type.value
    if mt == "HelpRequest":
        p = msg.payload or {}
        return f"Help: {str(p.get('question', ''))[:50]}"
    if mt == "HelpResponse":
        p = msg.payload or {}
        return f"Reply: {str(p.get('answer', ''))[:50]}"
    if mt == "StatusUpdate":
        p = msg.payload or {}
        return f"Status: {str(p.get('status', ''))[:50]}"
    if mt == "InterAgentMessage":
        p = msg.payload or {}
        return str(p.get('content', ''))[:60]
    if mt == "WhiteboardUpdate":
        return "Shared whiteboard entry"
    return mt
