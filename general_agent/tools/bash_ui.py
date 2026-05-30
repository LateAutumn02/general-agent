"""Bash UI rendering — ANSI parsing, output truncation, command classification.

Reference: cc-haha src/components/shell/OutputLine.tsx, src/utils/terminal.ts,
           src/tools/BashTool/BashTool.tsx (command classification)
"""

from __future__ import annotations

import re
import os
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants (matching cc-haha toolLimits.ts and terminal.ts)
# ---------------------------------------------------------------------------

MAX_STDOUT_LINES = 3               # Lines shown before truncation
MAX_CHARS_PROCESS_MULTIPLIER = 4   # × terminal_width to cap processing
MAX_COMMAND_DISPLAY_LINES = 2      # Command echo max lines
MAX_COMMAND_DISPLAY_CHARS = 160    # Command echo max chars
PADDING = 10                       # Space for "  ⎿ " prefix in output

# Commands where no output is expected (silent on success)
SILENT_COMMANDS: set[str] = {
    "mv", "cp", "rm", "mkdir", "rmdir", "touch",
    "chmod", "chown", "chgrp", "ln", "export",
    "unset", "alias", "source", ".", "cd",
}

# ANSI escape sequence regex: CSI / OSC / single-character escapes
_ANSI_RE = re.compile(
    r"\x1b\[[0-9;]*[A-Za-z]"   # CSI: ESC[0;31m etc.
    r"|\x1b\][^\x07]*\x07"     # OSC: ESC]0;title BEL
    r"|\x1b\][^\x1b]*\x1b\\\\" # OSC terminator
    r"|\x1b\][^\x07\x1b]*"     # OSC without terminator (malformed)
    r"|\033\[\?[0-9]+[hl]"     # DEC private modes
)

# SGR code regex: extracts the numeric codes from ESC[...m
_SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class BashOut:
    """Structured output from a bash command execution.

    Attributes:
        stdout:        Standard output text (raw, with ANSI codes)
        stderr:        Standard error text (raw, with ANSI codes)
        exit_code:     Process exit code (0 = success)
        interrupted:   Whether the user interrupted (Ctrl+C)
        timed_out:     Whether the command hit the timeout
        duration_ms:   Wall-clock execution time in milliseconds
        is_silent:     True if the command is in the SILENT_COMMANDS set
        is_image:      Whether the output is image data [v1: always False]
    """
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    interrupted: bool = False
    timed_out: bool = False
    duration_ms: int = 0
    is_silent: bool = False
    is_image: bool = False


# ---------------------------------------------------------------------------
# Command classification
# ---------------------------------------------------------------------------


def classify_command(command: str) -> str:
    """Classify a command as 'silent', 'search', 'read', 'list', or 'general'.

    Returns the classification string (used by commands like collapse grouping).
    """
    base = _extract_base_command(command)
    if base in SILENT_COMMANDS:
        return "silent"
    if base in ("find", "grep", "rg", "ag", "ack", "locate", "which", "whereis"):
        return "search"
    if base in (
        "cat", "head", "tail", "less", "more", "wc", "stat", "file",
        "strings", "jq", "awk", "cut", "sort", "uniq", "tr", "sed",
    ):
        return "read"
    if base in ("ls", "tree", "du", "dir"):
        return "list"
    return "general"


def is_silent_command(command: str) -> bool:
    """Check if the command is expected to produce no output on success."""
    return _extract_base_command(command) in SILENT_COMMANDS


def _extract_base_command(command: str) -> str:
    """Extract the base command name from a shell command string.

    Handles chained commands (&&, ;, |) by taking the first one.
    Handles sudo and env prefixes.
    """
    # Take first segment before && ; | or newline
    first = re.split(r"[;&|\n]", command.strip())[0].strip()
    parts = first.split()
    if not parts:
        return ""
    # Skip common prefixes
    i = 0
    for skip in ("sudo", "env", "nice", "nohup", "time"):
        if parts[i] == skip and i + 1 < len(parts):
            i += 1
        else:
            break
    # Return the basename of the command (strip path: /usr/bin/ls → ls)
    return os.path.basename(parts[i]) if i < len(parts) else parts[0]


# ---------------------------------------------------------------------------
# Command display truncation
# ---------------------------------------------------------------------------

def format_command_display(command: str) -> str:
    """Format a command for inline display, truncating long commands.

    Args:
        command: The raw shell command string.

    Returns:
        A display-suitable version (≤ 160 chars, ≤ 2 lines).
    """
    # Limit to 2 lines
    lines = command.split("\n")
    if len(lines) > MAX_COMMAND_DISPLAY_LINES:
        lines = lines[:MAX_COMMAND_DISPLAY_LINES]
    text = "  ".join(lines)  # Join continuation lines on one line

    # Truncate to 160 chars
    if len(text) > MAX_COMMAND_DISPLAY_CHARS:
        text = text[:MAX_COMMAND_DISPLAY_CHARS - 1] + "…"

    return text


# ---------------------------------------------------------------------------
# Output truncation
# ---------------------------------------------------------------------------


def format_output_lines(text: str, max_lines: int = MAX_STDOUT_LINES) -> tuple[str, int, int]:
    """Truncate output text. Returns (text, total_lines, shown_lines)."""
    if not text:
        return "", 0, 0
    clean = _strip_ansi(text)
    lines = clean.split("\n")
    total = len(lines)
    if total <= max_lines:
        return text, total, total
    shown = _take_n_lines_raw(text, max_lines)
    omitted = total - max_lines
    return f"{shown}\n\033[2m… +{omitted} lines\033[0m", total, max_lines


def render_bash_block(out: "BashOut") -> str:
    """Render bash output as a clean markdown-like code block.

    Produces output like::

        ┌──────────────────────────
        │ hello world
        │ line two
        └─ Done · 500ms

    stderr is prefixed with dim labels, stdout shown plain.
    """
    result: list[str] = []
    dim = "\033[2m"
    rst = "\033[0m"
    red = "\033[31m"

    # Top border
    result.append(f"  {dim}┌{'─' * 48}{rst}")

    # stdout
    if out.stdout:
        for line in out.stdout.split("\n"):
            result.append(f"  {dim}│{rst} {line}")
    # stderr
    if out.stderr:
        if out.stdout:
            result.append(f"  {dim}├─ stderr ─{rst}")
        for line in out.stderr.split("\n"):
            result.append(f"  {dim}│{rst} {red}{line}{rst}")

    # Bottom: status line
    status = _block_status(out)
    result.append(f"  {dim}└─{rst} {status}")

    return "\n".join(result)


def _block_status(out: "BashOut") -> str:
    """Build the bottom status line for a bash output block."""
    dim = "\033[2m"
    rst = "\033[0m"
    parts: list[str] = []

    if out.interrupted:
        parts.append(f"\033[33mInterrupted{rst}")
    elif out.timed_out:
        parts.append(f"\033[31mTimed out{rst}")
    elif out.exit_code != 0:
        parts.append(f"\033[31mexit {out.exit_code}{rst}")
    elif out.is_silent and not out.stdout and not out.stderr:
        parts.append(f"{dim}Done{rst}")
    elif not out.stdout and not out.stderr:
        parts.append(f"{dim}(no output){rst}")

    if out.duration_ms > 0:
        parts.append(f"{dim}{format_duration(out.duration_ms)}{rst}")

    return f"  {dim}·{rst}  ".join(parts) if len(parts) > 1 else parts[0] if parts else f"{dim}ok{rst}"


# ---------------------------------------------------------------------------
# ANSI handling
# ---------------------------------------------------------------------------


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences from text (public alias)."""
    return _strip_ansi(text)


def has_ansi(text: str) -> bool:
    """Quick check if text contains ANSI escape sequences."""
    return bool(_ANSI_RE.search(text))


def render_ansi(text: str) -> str:
    """Render ANSI-encoded text for terminal display.

    Currently a pass-through since most terminals handle ANSI natively.
    May add colorama wrapping for Windows in the future.
    """
    return text


# ---------------------------------------------------------------------------
# Duration formatting
# ---------------------------------------------------------------------------


def format_duration(ms: int) -> str:
    """Format milliseconds as a human-readable duration string.

    Examples:
        500  → "500ms"
        1200 → "1.2s"
        61000 → "1m 1s"
    """
    if ms < 1000:
        return f"{ms}ms"
    if ms < 60_000:
        return f"{ms / 1000:.1f}s"
    minutes = ms // 60_000
    seconds = (ms % 60_000) // 1000
    if seconds:
        return f"{minutes}m {seconds}s"
    return f"{minutes}m"


# ---------------------------------------------------------------------------
# Human-readable output summary
# ---------------------------------------------------------------------------


def summarize_result(out: BashOut) -> str:
    """Produce a human-readable summary line for the bash result.

    Called by the agent loop / REPL to display what happened.
    """
    parts: list[str] = []

    # Duration
    if out.duration_ms > 0:
        parts.append(format_duration(out.duration_ms))

    # Exit status
    if out.interrupted:
        parts.append("\033[33mInterrupted\033[0m")
    elif out.timed_out:
        parts.append("\033[31mTimed out\033[0m")
    elif out.exit_code != 0:
        parts.append(f"\033[31mexit {out.exit_code}\033[0m")
    elif out.is_silent and not out.stdout and not out.stderr:
        parts.append("\033[2mDone\033[0m")

    return " ".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return _ANSI_RE.sub("", text)


def _take_n_lines_raw(text: str, n: int) -> str:
    """Take the first N lines from raw text (ANSI-preserving).

    Non-ANSI newlines are the splitting point. ANSI sequences are
    passed through intact.
    """
    # Simple approach: iterate characters, counting newlines, stop at N
    result: list[str] = []
    newlines = 0
    in_ansi = False
    for ch in text:
        result.append(ch)
        if ch == "\x1b":
            in_ansi = True
        elif in_ansi and ch.isalpha():
            in_ansi = False  # CSI terminator
        elif not in_ansi and ch == "\n":
            newlines += 1
            if newlines >= n:
                break
    return "".join(result).rstrip("\n")
