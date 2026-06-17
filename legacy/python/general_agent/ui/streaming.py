"""Streaming text handler — buffers agent output and flushes periodically.

Reference: TunaCode streaming.py
"""

from __future__ import annotations

import time

from textual.widgets import Static


class StreamingHandler:
    """Buffers incoming text deltas and flushes them to a Static widget.

    Flushes happen on every delta, but the widget only updates the visible
    portion when ``flush()`` is called.  This keeps the UI responsive without
    re-rendering on every keystroke of incoming text.

    Usage::

        handler = StreamingHandler(widget)
        handler.callback("token ")   # accumulate
        handler.callback("stream")   # accumulate
        handler.flush()              # show everything
        handler.reset()              # clear for next request
    """

    def __init__(self, widget: Static, throttle_ms: float = 100.0) -> None:
        self._widget: Static = widget
        self._text: str = ""
        self._throttle_ms: float = throttle_ms
        self._last_update: float = 0.0
        self._max_visible_chars: int = 4000

    def callback(self, chunk: str) -> None:
        """Accumulate a text delta and throttle-flush."""
        self._text += chunk
        now = time.monotonic() * 1000.0
        if now - self._last_update >= self._throttle_ms:
            self._flush()
            self._last_update = now

    def _flush(self) -> None:
        if not self._widget.is_attached:
            return
        self._widget.add_class("active")
        visible = self._text[-self._max_visible_chars:]
        if len(self._text) > self._max_visible_chars:
            visible = "... streaming output truncated to latest text ...\n" + visible
        self._widget.update(visible)

    def flush(self) -> None:
        """Force-flush all accumulated text."""
        self._flush()

    def reset(self) -> None:
        """Clear the buffer and hide the widget."""
        self._text = ""
        if self._widget.is_attached:
            self._widget.remove_class("active")
            self._widget.update("")
