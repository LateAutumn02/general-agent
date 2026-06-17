"""Rich-based terminal rendering helpers.

These functions are called by ``loop.py`` and return Rich renderables
(``Text``, ``Panel``, etc.) that can be consumed by both:

- The Textual UI (``ChatContainer.write()``)
- The legacy print-REPL (by converting to console markup)

All tool call / bash rendering is delegated to ``bash_ui.py``.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from general_agent.tools.bash_ui import BashOut, render_bash_panel, render_tool_call

_console = Console(highlight=False)


# ---------------------------------------------------------------------------
# Section separators (non-Textual / headless use)
# ---------------------------------------------------------------------------


def separator(label: str = "") -> None:
    """Print a dim horizontal rule."""
    if label:
        _console.rule(f"[dim]{label}[/dim]", style="dim")
    else:
        _console.rule(style="dim")


# ---------------------------------------------------------------------------
# Tool call dot
# ---------------------------------------------------------------------------


def tool_call(name: str, detail: str = "", success: bool | None = None):
    """Return a Rich ``Text`` for a tool call status line.

    Used by ``loop.py:_execute_tool`` to display tool execution progress.

    Args:
        name:    Tool name (Bash, Read, Edit, etc.)
        detail:  Key parameter (command, file_path, etc.)
        success: True=green dot, False=red dot, None=gray dot
    """
    return render_tool_call(name, detail, success)


# ---------------------------------------------------------------------------
# Bash output block
# ---------------------------------------------------------------------------


def bash_output(
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    duration_ms: int = 0,
    interrupted: bool = False,
    timed_out: bool = False,
) -> Panel:
    """Render bash output as a Rich Panel. Delegates to bash_ui."""
    out = BashOut(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        interrupted=interrupted,
        timed_out=timed_out,
        duration_ms=duration_ms,
    )
    return render_bash_panel(out)


# ---------------------------------------------------------------------------
# Code diff display
# ---------------------------------------------------------------------------


def code_diff(file_path: str, old: str, new: str) -> Panel | None:
    """Render a code change as a VS Code-style diff panel."""
    parts: list[Text] = []
    if old:
        for line in old.split("\n"):
            parts.append(Text(line, style="on red"))
    if new:
        for line in new.split("\n"):
            parts.append(Text(line, style="on green"))
    if not parts:
        return None
    content = Text()
    for i, p in enumerate(parts):
        if i > 0:
            content.append("\n")
        content.append(p)
    return Panel(content, title=f"[bold]{file_path}[/bold]", title_align="left",
                  border_style="dim", padding=(0, 1))


# ---------------------------------------------------------------------------
# File read preview
# ---------------------------------------------------------------------------


def file_preview(file_path: str, content: str, line_start: int = 0) -> Panel:
    """Show a file read result with syntax highlighting."""
    ext = file_path.rsplit(".", 1)[-1] if "." in file_path else ""
    lang_map = {
        "py": "python", "js": "javascript", "ts": "typescript",
        "json": "json", "yaml": "yaml", "yml": "yaml",
        "md": "markdown", "html": "html", "css": "css",
        "toml": "toml", "sh": "bash", "rs": "rust", "go": "go",
    }
    lang = lang_map.get(ext, "text")

    if not content.strip():
        return Panel("[dim](empty)[/dim]", title=f"[bold]{file_path}[/bold]", border_style="dim")

    lines = content.split("\n")
    if len(lines) > 20:
        content = "\n".join(lines[:20]) + f"\n[dim]… +{len(lines) - 20} lines[/dim]"

    return Panel(
        Syntax(content, lang, theme="monokai", line_numbers=False, word_wrap=True),
        title=f"[bold]{file_path}[/bold]",
        title_align="left",
        border_style="dim",
        padding=(0, 1),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def print_markup(markup: str) -> None:
    """Print Rich markup immediately (for non-Textual one-shot mode)."""
    _console.print(markup)


def print_text(text: str) -> None:
    """Print a text chunk immediately (for streaming in non-Textual mode)."""
    _console.print(text, end="")
