"""Task notification - display task completion/failure to user.

Matching cc-haha enqueueAgentNotification pattern.
"""

from __future__ import annotations

from general_agent.tasks.task import TaskState, TaskStatus


def format_notification(task: TaskState) -> str | None:
    """Format a task notification message for display.

    Returns:
        Formatted string or None if task should not be notified.
    """
    if task.status == TaskStatus.COMPLETED:
        return format_completed(task)
    if task.status == TaskStatus.FAILED:
        return format_failed(task)
    if task.status == TaskStatus.KILLED:
        return format_killed(task)
    return None


def format_completed(task: TaskState) -> str:
    desc = task.description or "task"
    duration = ""
    if task.end_time and task.start_time:
        duration = f" in {task.end_time - task.start_time:.1f}s"
    return (
        f"\033[32m[Task {task.id}]\033[0m {desc} completed{duration} "
        f"({task.tool_use_count} tools, {task.total_input_tokens + task.total_output_tokens} tokens)"
    )


def format_failed(task: TaskState) -> str:
    desc = task.description or "task"
    error = task.error or "unknown error"
    return f"\033[31m[Task {task.id}]\033[0m {desc} failed: {error}"


def format_killed(task: TaskState) -> str:
    desc = task.description or "task"
    return f"\033[33m[Task {task.id}]\033[0m {desc} was killed"
