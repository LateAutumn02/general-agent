"""Task system - matches cc-haha Task.ts + LocalAgentTask.tsx patterns.

Async task lifecycle: pending → running → completed/failed/killed.
Progress tracking with cumulative input + per-turn output tokens.

Reference: cc-haha src/Task.ts, src/tasks/LocalAgentTask/LocalAgentTask.tsx
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable


class TaskType(StrEnum):
    LOCAL_AGENT = "local_agent"
    LOCAL_BASH = "local_bash"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


TERMINAL_STATUS = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED}


@dataclass
class TaskState:
    """Base task state, shared by all task types."""

    id: str = field(default_factory=lambda: "a" + uuid.uuid4().hex[:8])
    type: TaskType = TaskType.LOCAL_AGENT
    status: TaskStatus = TaskStatus.PENDING
    description: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    error: str | None = None
    tool_use_id: str | None = None  # Parent tool invocation ID

    # Agent-specific
    prompt: str = ""
    agent_type: str = ""
    model: str = ""
    result: Any = None
    messages: list[dict[str, Any]] = field(default_factory=list)

    # Progress
    tool_use_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Inter-agent messaging queue (SendMessage)
    pending_messages: list[str] = field(default_factory=list)

    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUS


class TaskRegistry:
    """Manages all running/completed tasks (cc-haha AppState.tasks pattern)."""

    def __init__(self):
        self._tasks: dict[str, TaskState] = {}

    def create(
        self,
        task_type: TaskType = TaskType.LOCAL_AGENT,
        **kwargs,
    ) -> TaskState:
        task = TaskState(type=task_type, **kwargs)
        self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> TaskState | None:
        return self._tasks.get(task_id)

    def update(self, task_id: str, **kwargs) -> TaskState | None:
        task = self._tasks.get(task_id)
        if task and not task.is_terminal():
            for k, v in kwargs.items():
                setattr(task, k, v)
            return task
        return None

    def complete(
        self, task_id: str, result: Any = None, error: str | None = None
    ) -> None:
        task = self._tasks.get(task_id)
        if task and not task.is_terminal():
            task.end_time = time.time()
            if error:
                task.status = TaskStatus.FAILED
                task.error = error
            else:
                task.status = TaskStatus.COMPLETED
                task.result = result

    def kill(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task and not task.is_terminal():
            task.status = TaskStatus.KILLED
            task.end_time = time.time()

    def list_running(self) -> list[TaskState]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]

    def all(self) -> list[TaskState]:
        return list(self._tasks.values())

    def drain_pending_messages(self, task_id: str) -> list[str]:
        """Drain queued messages (called at tool-round boundaries)."""
        task = self._tasks.get(task_id)
        if not task:
            return []
        msgs = task.pending_messages
        task.pending_messages = []
        return msgs
