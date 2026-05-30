"""Rich-based terminal rendering for general-agent.

Matches cc-haha's visual style:
  - Tool calls with colored status dots (green=ok, red=error)
  - Bash output blocks with borders
  - Code diffs (red bg = removed, green bg = added)
  - Separator lines between sections
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich import box

_console = Console(highlight=False)


# ---------------------------------------------------------------------------
# Section separators
# ---------------------------------------------------------------------------


def separator(label: str = "") -> None:
    """Print a dim horizontal rule, optionally with a label."""
    if label:
        _console.rule(f"[dim]{label}[/dim]", style="dim")
    else:
        _console.rule(style="dim")


# ---------------------------------------------------------------------------
# User prompt
# ---------------------------------------------------------------------------


def user_prompt(text: str) -> None:
    """Render the user's input on a dim background after they press enter."""
    separator()
    _console.print(f"  [on grey15]{text}[/on grey15]")


def prompt_line() -> None:
    """Draw the input prompt separator line before user starts typing."""
    separator()


# ---------------------------------------------------------------------------
# Tool call dot (success / failure)
# ---------------------------------------------------------------------------


def tool_call(name: str, detail: str = "", success: bool | None = None) -> str:
    """Return an ANSI string for a tool call line.

    Args:
        name:    Tool name (Bash, Read, Edit, etc.)
        detail:  Key parameter (command, file_path, etc.)
        success: True=green dot, False=red dot, None=gray dot (pending)

    Returns:
        ANSI-encoded string, ready for plain print().
    """
    if success is True:
        dot = "\033[32m●\033[0m"
    elif success is False:
        dot = "\033[31m●\033[0m"
    else:
        dot = "\033[2m○\033[0m"

    if detail:
        return f"  {dot} \033[33m{name}\033[0m(\033[2m{detail}\033[0m)"
    return f"  {dot} \033[33m{name}\033[0m"


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
) -> None:
    """Render bash command output as a bordered block.

    stdout shown normally, stderr in red inside the same block.
    Status line at bottom: Done / exit N / Interrupted + duration.
    """
    content = Text()

    if stdout:
        for line in stdout.split("\n"):
            content.append(f"{line}\n", style="")

    if stderr:
        if stdout:
            content.append("--- stderr ---\n", style="dim")
        for line in stderr.split("\n"):
            content.append(f"{line}\n", style="red")

    content.rstrip()

    # Status
    status = _bash_status(exit_code, duration_ms, interrupted, timed_out)

    # Border style
    if exit_code != 0 or timed_out or interrupted:
        border = "red"
    else:
        border = "dim green"

    _console.print(
        Panel(content, title="stdout", title_align="left",
              subtitle=status, subtitle_align="right",
              border_style=border, padding=(0, 1)),
    )


def _bash_status(exit_code: int, duration_ms: int,
                 interrupted: bool, timed_out: bool) -> str:
    """Build the status subtitle for bash output blocks."""
    parts = []
    if interrupted:
        parts.append("[yellow]Interrupted[/yellow]")
    elif timed_out:
        parts.append("[red]Timed out[/red]")
    elif exit_code != 0:
        parts.append(f"[red]exit {exit_code}[/red]")
    else:
        parts.append("[green]Done[/green]")

    if duration_ms > 0:
        ms = duration_ms
        if ms < 1000:
            parts.append(f"[dim]{ms}ms[/dim]")
        elif ms < 60000:
            parts.append(f"[dim]{ms/1000:.1f}s[/dim]")
        else:
            m = ms // 60000
            s = (ms % 60000) // 1000
            parts.append(f"[dim]{m}m {s}s[/dim]")

    return " [dim]·[/dim] ".join(parts)


# ---------------------------------------------------------------------------
# Code diff display (VS Code style)
# ---------------------------------------------------------------------------


def code_diff(file_path: str, old: str, new: str) -> None:
    """Render a code change as a VS Code-style diff.

    Args:
        file_path: The file that was edited.
        old:       The removed text (red background).
        new:       The inserted text (green background).
    """
    parts = []
    if old:
        for line in old.split("\n"):
            parts.append(Text(line, style="on red"))
    if new:
        for line in new.split("\n"):
            parts.append(Text(line, style="on green"))

    if not parts:
        return

    content = Text()
    for i, p in enumerate(parts):
        if i > 0:
            content.append("\n")
        content.append(p)

    _console.print(
        Panel(content, title=f"[bold]{file_path}[/bold]", title_align="left",
              border_style="dim", padding=(0, 1)),
    )


# ---------------------------------------------------------------------------
# File read preview
# ---------------------------------------------------------------------------


def file_preview(file_path: str, content: str, line_start: int = 0) -> None:
    """Show a file read result with syntax highlighting if possible."""
    # Guess language from extension
    ext = file_path.rsplit(".", 1)[-1] if "." in file_path else ""
    lang_map = {"py": "python", "js": "javascript", "ts": "typescript",
                "json": "json", "yaml": "yaml", "yml": "yaml",
                "md": "markdown", "html": "html", "css": "css",
                "toml": "toml", "sh": "bash", "rs": "rust", "go": "go"}
    lang = lang_map.get(ext, "text")

    if not content.strip():
        _console.print(f"  [dim](empty)[/dim]")
        return

    # Truncate long content
    lines = content.split("\n")
    if len(lines) > 20:
        content = "\n".join(lines[:20])
        content += f"\n[dim]… +{len(lines) - 20} lines[/dim]"

    _console.print(
        Panel(Syntax(content, lang, theme="monokai", line_numbers=False,
                     word_wrap=True),
              title=f"[bold]{file_path}[/bold]",
              title_align="left",
              border_style="dim", padding=(0, 1)),
    )


# ---------------------------------------------------------------------------
# Thinking indicator
# ---------------------------------------------------------------------------


def thinking() -> None:
    """Print the 'Thinking...' indicator."""
    _console.print("  [dim]Thinking...[/dim]", end="\r")


def thought(seconds: float) -> None:
    """Replace the thinking indicator with elapsed time."""
    _console.print(f"  [dim]Thought for {seconds:.0f}s[/dim]")


# Helpers

def print_markup(markup: str) -> None:
    _console.print(markup)


def print_text(text: str) -> None:
    """Print a text chunk immediately (for streaming)."""
    _console.print(text, end="")
