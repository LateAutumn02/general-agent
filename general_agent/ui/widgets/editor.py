"""Input editor widget — single-line with Enter-to-submit.

Reference: TunaCode widgets/editor.py
"""

from __future__ import annotations

from textual.binding import Binding
from textual.widgets import Input

from general_agent.ui.widgets.messages import EditorSubmitRequested


class PromptInput(Input):
    """Single-line editor.  ``!`` prefix enters bash-mode (green outline)."""

    BINDINGS = [
        Binding("enter", "submit", "Submit", show=False),
    ]

    def __init__(self) -> None:
        super().__init__(placeholder="Type a message, or / for commands…")

    # -- actions ----------------------------------------------------

    async def action_submit(self) -> None:
        text = self.value
        if not text.strip():
            return
        self.post_message(EditorSubmitRequested(text=text.strip(), raw_text=text))
        self.value = ""

    # -- reactives --------------------------------------------------

    def watch_value(self, value: str) -> None:
        """Toggle bash-mode CSS class as the user types."""
        if value.startswith("!"):
            self.add_class("bash-mode")
        else:
            self.remove_class("bash-mode")
