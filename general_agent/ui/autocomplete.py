"""Slash-command autocomplete dropdown for the editor.

Reference: TunaCode widgets/command_autocomplete.py + autocomplete_positioning.py
"""

from __future__ import annotations

from textual.widgets import Input
from textual_autocomplete import AutoComplete, DropdownItem, TargetState


# Command list: (name, description)
_COMMANDS: list[tuple[str, str]] = [
    ("help", "Show available commands"),
    ("exit", "Exit general-agent"),
    ("quit", "Exit general-agent"),
    ("model", "Switch or show current model"),
    ("clear", "Clear conversation history"),
    ("session", "Show session info"),
    ("compact", "Compress conversation context"),
    ("memory", "Memory operations (list/on/off/refresh)"),
    ("sandbox", "Toggle sandbox mode"),
    ("resume", "Resume a previous session"),
    ("context", "Show context window settings"),
]

COMMAND_PREFIX = "/"


def _get_prefix(text: str, cursor: int) -> str | None:
    """Extract the command fragment before cursor, or None if not editing a command name."""
    if not text.startswith(COMMAND_PREFIX):
        return None
    region = text[len(COMMAND_PREFIX): cursor]
    if " " in region:
        return None  # typing arguments, not the command name
    return region


def _is_exact_match(prefix: str) -> bool:
    return any(prefix.lower() == name.lower() for name, _ in _COMMANDS)


class CommandAutoComplete(AutoComplete):
    """Dropdown that suggests slash commands as the user types."""

    def __init__(self, target: Input) -> None:
        super().__init__(target)

    def get_search_string(self, target_state: TargetState) -> str:
        prefix = _get_prefix(target_state.text, target_state.cursor_position)
        return prefix or ""

    def should_show_dropdown(self, search_string: str) -> bool:  # noqa: ARG002
        del search_string
        try:
            count = self.option_list.option_count
        except Exception:
            return False
        if count == 0:
            return False
        ts = self._get_target_state()
        prefix = _get_prefix(ts.text, ts.cursor_position)
        return prefix is not None and not _is_exact_match(prefix)

    def get_candidates(self, target_state: TargetState) -> list[DropdownItem]:
        prefix = _get_prefix(target_state.text, target_state.cursor_position)
        if prefix is None:
            return []
        search = prefix.lower()
        return [
            DropdownItem(main=f"/{name}  —  {desc}")
            for name, desc in _COMMANDS
            if name.startswith(search)
        ]

    def apply_completion(self, value: str, state: TargetState) -> None:
        cmd = value.split("  —  ", 1)[0]
        trailing = state.text[state.cursor_position:].lstrip()
        new_text = cmd + " " + trailing
        self.target.value = new_text
        self.target.cursor_position = len(cmd) + 1
