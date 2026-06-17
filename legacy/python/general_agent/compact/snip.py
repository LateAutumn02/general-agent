"""Snip compact - removes old messages from the front of conversation.

Matching cc-haha snipCompact.ts pattern.
Removes old messages while keeping state intact. Simpler than full compact.
"""

from general_agent.compact.constants import estimate_tokens
from general_agent.compact.constants import get_auto_compact_threshold

# Max tokens to keep after snipping
SNIP_TARGET_TOKENS = 50_000


def snip_messages(
    messages: list[dict],
    target_tokens: int = SNIP_TARGET_TOKENS,
    model: str = "",
) -> tuple[list[dict], int]:
    """Remove oldest messages until total is under target_tokens.

    Never removes the last user message (keeps context for the current turn).
    Returns (snipped_messages, tokens_freed).
    """
    if not messages:
        return messages, 0

    pre_tokens = estimate_tokens(messages)
    if pre_tokens <= target_tokens:
        return messages, 0

    # Find the last user message index (don't snip beyond it)
    last_user_idx = len(messages) - 1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break

    # Remove messages from the front until we're under target
    for cut_idx in range(0, last_user_idx):
        remaining = messages[cut_idx:]
        remaining_tokens = estimate_tokens(remaining)
        if remaining_tokens <= target_tokens:
            return remaining, pre_tokens - remaining_tokens

    # If we can't get under, return last user message + everything after
    result = messages[last_user_idx:]
    return result, pre_tokens - estimate_tokens(result)


def try_snip(
    messages: list[dict],
    model: str = "",
    pct: int = 80,
) -> tuple[list[dict], int]:
    """Try to snip messages if near threshold. Returns (messages, tokens_freed)."""
    from general_agent.compact.constants import threshold_from_pct

    threshold = threshold_from_pct(pct)
    tokens = estimate_tokens(messages)

    if tokens >= threshold:
        target = int(threshold * 0.6)  # Snip target: 60% of threshold
        return snip_messages(messages, target_tokens=target, model=model)

    return messages, 0
