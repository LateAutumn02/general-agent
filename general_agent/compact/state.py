"""Compact state types - matching cc-haha compact.ts types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AutoCompactTrackingState:
    """Tracks compact state across loop iterations."""
    compacted: bool = False
    turn_counter: int = 0
    consecutive_failures: int = 0


@dataclass
class CompactionResult:
    """Result of a compact operation."""
    summary_text: str = ""
    pre_compact_tokens: int = 0
    post_compact_tokens: int = 0
    messages_summarized: int = 0


@dataclass
class TokenWarningState:
    """Token usage relative to thresholds."""
    current_tokens: int = 0
    threshold: int = 0
    is_above_warning: bool = False
    is_above_compact: bool = False
    is_at_blocking: bool = False
    percent_left: int = 100


@dataclass
class SystemCompactBoundaryMessage:
    """Marks the boundary between old (compacted) and new messages."""
    role: str = "system"
    subtype: str = "compact_boundary"
    content: str = "Conversation compacted."
