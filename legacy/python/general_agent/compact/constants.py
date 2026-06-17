"""Compact thresholds and window calculation.

cc-haha ratios scaled for DeepSeek 1M context (vs Claude 200K).
- AUTOCOMPACT_BUFFER: 6.5% of effective (cc-haha: 13K/200K)
- WARNING_BUFFER: 10% of effective (cc-haha: 20K/200K)
"""

from general_agent.constants.models import MODEL_CONTEXT_WINDOW

# cc-haha defaults scaled proportionally to 1M
AUTOCOMPACT_BUFFER_TOKENS = 65_000
WARNING_THRESHOLD_BUFFER_TOKENS = 100_000
MANUAL_COMPACT_BUFFER_TOKENS = 3_000
MAX_OUTPUT_TOKENS_FOR_SUMMARY = 20_000
MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3


def get_effective_context_window_size(model: str = "") -> int:
    """Effective context = 1M - 20K output = 980K."""
    return MODEL_CONTEXT_WINDOW - 20_000


def get_auto_compact_threshold(model: str = "") -> int:
    """Auto-compact: 980K - 65K = 915K."""
    return get_effective_context_window_size(model) - AUTOCOMPACT_BUFFER_TOKENS


def get_warning_threshold(model: str = "") -> int:
    """Warning: 915K - 100K = 815K."""
    return get_auto_compact_threshold(model) - WARNING_THRESHOLD_BUFFER_TOKENS


def threshold_from_pct(pct: int) -> int:
    """Convert a percentage to a token threshold."""
    return int(MODEL_CONTEXT_WINDOW * pct / 100)


def estimate_tokens(messages: list[dict]) -> int:
    """Rough token estimation: ~4 chars per token."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text", "") or block.get("content", "") or str(block)
                    total += len(text)
    return total // 4
