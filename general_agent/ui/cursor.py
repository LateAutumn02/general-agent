"""Cross-platform terminal cursor control.

On Windows, uses kernel32 SetConsoleCursorPosition to move the cursor
(matching what cc-haha does via Ink's Windows Console backend).
On POSIX, uses ANSI escape sequences.
"""

from __future__ import annotations

import os
import sys


def cursor_up(n: int = 1) -> None:
    """Move cursor up N lines. Works on Windows (kernel32) and POSIX (ANSI)."""
    if os.name == "nt":
        _win_cursor_up(n)
    else:
        sys.stdout.write(f"\033[{n}A")
        sys.stdout.flush()


def cursor_down(n: int = 1) -> None:
    """Move cursor down N lines."""
    if os.name == "nt":
        _win_cursor_down(n)
    else:
        sys.stdout.write(f"\033[{n}B")
        sys.stdout.flush()


def cursor_to_column(col: int) -> None:
    """Move cursor to column (1-indexed)."""
    if os.name == "nt":
        _win_cursor_to_column(col)
    else:
        sys.stdout.write(f"\033[{col}G")
        sys.stdout.flush()


def cursor_to(x: int, y: int) -> None:
    """Move cursor to absolute position (column x, row y), 1-indexed."""
    if os.name == "nt":
        _win_cursor_to(x, y)
    else:
        sys.stdout.write(f"\033[{y};{x}H")
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Windows implementation via kernel32
# ---------------------------------------------------------------------------


def _win_cursor_up(n: int) -> None:
    import ctypes
    handle = ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
    info = _get_console_info(handle)
    new_y = max(0, info.y - n)
    ctypes.windll.kernel32.SetConsoleCursorPosition(handle, new_y << 16 | info.x)


def _win_cursor_down(n: int) -> None:
    import ctypes
    handle = ctypes.windll.kernel32.GetStdHandle(-11)
    info = _get_console_info(handle)
    new_y = info.y + n
    ctypes.windll.kernel32.SetConsoleCursorPosition(handle, new_y << 16 | info.x)


def _win_cursor_to_column(col: int) -> None:
    import ctypes
    handle = ctypes.windll.kernel32.GetStdHandle(-11)
    info = _get_console_info(handle)
    ctypes.windll.kernel32.SetConsoleCursorPosition(handle, info.y << 16 | (col - 1))


def _win_cursor_to(x: int, y: int) -> None:
    import ctypes
    handle = ctypes.windll.kernel32.GetStdHandle(-11)
    ctypes.windll.kernel32.SetConsoleCursorPosition(handle, (y - 1) << 16 | (x - 1))


def _get_console_info(handle: int):
    import ctypes
    class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong),
            ("dwCursorPosition", ctypes.c_ulong),
            ("wAttributes", ctypes.c_ushort),
            ("srWindow", ctypes.c_ushort * 4),
            ("dwMaximumWindowSize", ctypes.c_ulong),
        ]
    info = CONSOLE_SCREEN_BUFFER_INFO()
    ctypes.windll.kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info))
    pos = info.dwCursorPosition
    return type('Pos', (), {'x': pos & 0xFFFF, 'y': pos >> 16})()
