"""Request bridge — translates ``run_agent()`` callbacks into Textual messages.

Reference: TunaCode request_bridge.py + repl_support.py
"""

from __future__ import annotations

from textual.message import Message

from general_agent.tools.bash_ui import strip_ansi


# -- Messages ------------------------------------------------------


class ProgressMessage(Message, bubble=True):
    """Plain-text progress line (tool status dot)."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text


class ToolDisplayMessage(Message, bubble=True):
    """Rich renderable from a finished tool result."""

    def __init__(self, renderable) -> None:
        super().__init__()
        self.renderable = renderable


class StreamChunk(Message, bubble=True):
    """One incremental text delta from the streaming API."""

    def __init__(self, chunk: str) -> None:
        super().__init__()
        self.chunk = chunk


class StreamEnd(Message, bubble=True):
    """Streaming is complete — finalise display."""


class PermissionRequest(Message, bubble=True):
    """Ask user for tool execution permission."""

    def __init__(self, tool_name: str, args: dict) -> None:
        super().__init__()
        self.tool_name = tool_name
        self.args = args


# -- Bridge --------------------------------------------------------


class RequestBridge:
    """Wraps ``run_agent()`` callbacks so they post Textual messages.

    ``on_progress`` receives either a Rich renderable (from the updated
    ``render.py`` / ``bash_ui.py``) or a legacy ANSI string.  We dispatch
    accordingly so the App can render directly into ChatContainer.
    """

    def __init__(self, app) -> None:
        self.app = app

    # -- callbacks (called by run_agent) ---------------------------

    def on_progress(self, msg) -> None:
        """Tool status dot or bash output panel."""
        if isinstance(msg, str):
            clean = strip_ansi(msg).strip()
            if clean:
                self.app.post_message(ProgressMessage(clean))
        else:
            self.app.post_message(ToolDisplayMessage(msg))

    def on_text(self, chunk: str) -> None:
        """Streaming text delta."""
        if chunk:
            self.app.post_message(StreamChunk(chunk))

    def on_stream_end(self) -> None:
        """Called after run_agent() returns."""
        self.app.post_message(StreamEnd())

    async def on_permission(self, tool_name: str, args: dict) -> bool:
        """Block until the user approves / denies the tool call."""
        import asyncio

        event = asyncio.Event()
        result: list[bool] = [False]
        self.app._pending_permission = (tool_name, str(args)[:120], event, result)
        self.app.post_message(PermissionRequest(tool_name, args))
        await event.wait()
        return result[0]
