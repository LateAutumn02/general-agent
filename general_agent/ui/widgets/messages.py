"""Textual message classes for widget-to-app communication.

Reference: TunaCode widgets/messages.py
"""

from __future__ import annotations

from textual.message import Message


class EditorSubmitRequested(Message, bubble=True):
    """User pressed Enter with non-empty input."""

    def __init__(self, text: str, raw_text: str = "") -> None:
        super().__init__()
        self.text = text
        self.raw_text = raw_text or text


class ToolResultDisplay(Message, bubble=True):
    """Request to display a tool result in the chat container."""

    def __init__(
        self,
        *,
        tool_name: str,
        status: str,  # "running" | "completed" | "failed"
        args: dict | None = None,
        result_text: str | None = None,
        duration_ms: float | None = None,
    ) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.status = status
        self.args = args or {}
        self.result_text = result_text
        self.duration_ms = duration_ms


class SystemNoticeDisplay(Message, bubble=True):
    """Show a system-level notice in the chat."""

    def __init__(self, notice: str) -> None:
        super().__init__()
        self.notice = notice


class CompactionStatusChanged(Message, bubble=True):
    """Notify the status bar when compaction starts/stops."""

    def __init__(self, active: bool) -> None:
        super().__init__()
        self.active = active
