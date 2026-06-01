"""Top resource bar — model, token gauge, session cost.

Reference: TunaCode widgets/resource_bar.py
"""

from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from general_agent.ui.model_display import format_model_for_display


class StatusBar(Static):
    """One-line top bar summarising the current session.

    Format: ``● 73%  -  DeepSeek V4 Pro  -  $0.02``
    """

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        dock: top;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__("Loading...")
        self._tokens: int = 0
        self._max_tokens: int = 200000
        self._model: str = ""
        self._session_cost: float = 0.0
        self._compacting: bool = False

    # -- public API -------------------------------------------------

    def update_stats(
        self,
        *,
        tokens: int | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
        session_cost: float | None = None,
    ) -> None:
        if tokens is not None:
            self._tokens = tokens
        if max_tokens is not None:
            self._max_tokens = max(1, max_tokens)
        if model is not None:
            self._model = model
        if session_cost is not None:
            self._session_cost = session_cost
        self._refresh()

    def set_compacting(self, active: bool) -> None:
        self._compacting = active
        self._refresh()

    # -- internals --------------------------------------------------

    def _refresh(self) -> None:
        pct = self._remaining_pct()
        ch, color = self._circle(pct)
        model = format_model_for_display(self._model) if self._model else "---"

        parts: list[tuple[str, str]] = [
            (ch, color),
            (f" {pct:.0f}%", color),
            ("  -  ", "dim"),
            (model, "bold cyan"),
            ("  -  ", "dim"),
            (f"${self._session_cost:.2f}", "bold green"),
        ]
        if self._compacting:
            parts.append(("  Compacting...", "yellow"))

        self.update(Text.assemble(*parts))

    def _remaining_pct(self) -> float:
        if self._max_tokens <= 0:
            return 0.0
        return max(0.0, min(100.0, (self._max_tokens - self._tokens) / self._max_tokens * 100))

    @staticmethod
    def _circle(pct: float) -> tuple[str, str]:
        if pct > 87.5:
            c = "●"
        elif pct > 62.5:
            c = "◕"
        elif pct > 37.5:
            c = "◑"
        elif pct > 12.5:
            c = "◔"
        else:
            c = "○"
        color = "green" if pct > 60 else ("yellow" if pct > 30 else "red")
        return c, color
