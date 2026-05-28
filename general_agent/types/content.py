"""Message and content block types matching Anthropic API format.

Reference: cc-haha src/agents/agent-data-structure.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# ---------------------------------------------------------------------------
# ContentBlock types
# ---------------------------------------------------------------------------


@dataclass
class TextBlock:
    """A plain text content block in a message."""

    type: Literal["text"] = "text"
    text: str = ""


@dataclass
class ToolUseBlock:
    """A tool call request from the assistant."""

    type: Literal["tool_use"] = "tool_use"
    id: str = ""
    name: str = ""
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResultBlock:
    """A tool execution result injected as a user message."""

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str = ""
    content: str = ""
    is_error: bool = False


# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------


@dataclass
class UserMessage:
    """A message from the user.

    content can be a plain string or a list of ContentBlock objects.
    """

    role: Literal["user"] = "user"
    content: str | list[TextBlock | ToolResultBlock] = ""


@dataclass
class AssistantMessage:
    """A message from the assistant (AI response).

    Yields for each content_block_stop event during streaming.
    Usage and stop_reason are mutated by the message_delta handler after yielding.
    """

    role: Literal["assistant"] = "assistant"
    content: list[TextBlock | ToolUseBlock] = field(default_factory=list)
    stop_reason: str | None = None  # "end_turn" | "max_tokens" | "tool_use"
    usage: dict[str, int] = field(default_factory=dict)
    is_api_error_message: bool = False


@dataclass
class SystemMessage:
    """A system-level message (instructions, context).

    Injected with role="user" for API compatibility.
    """

    role: Literal["user"] = "user"
    content: str = ""
    subtype: str | None = None  # e.g. "compact_boundary"


@dataclass
class AttachmentMessage:
    """Attachment injection (memory, skill prompt, file content, hook)."""

    role: Literal["user"] = "user"
    content: str = ""
    attachment_type: Literal["memory", "skill", "file", "hook"] = "file"


# ---------------------------------------------------------------------------
# Stream event
# ---------------------------------------------------------------------------


@dataclass
class StreamEvent:
    """Wrapper for raw SSE events yielded during streaming."""

    type: Literal["stream_event"] = "stream_event"
    event: Any = None  # Raw event object from the Anthropic SDK


# ---------------------------------------------------------------------------
# Union types
# ---------------------------------------------------------------------------

# Any message that can appear in the conversation
Message = UserMessage | AssistantMessage | SystemMessage | AttachmentMessage

# A content block within a message
ContentBlock = TextBlock | ToolUseBlock | ToolResultBlock
