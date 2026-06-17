"""Reactive compact - responds to API 413 (prompt-too-long) errors.

Matching cc-haha reactiveCompact.ts pattern.
When the API returns 413, strip old messages and retry.
"""

import logging
from general_agent.compact.snip import snip_messages, SNIP_TARGET_TOKENS

logger = logging.getLogger("general_agent.compact.reactive")


def try_reactive_compact(
    messages: list[dict],
    error_message: str = "",
) -> tuple[list[dict], bool]:
    """Attempt to recover from a prompt-too-long error by snipping messages.

    Called when the API returns 413 or context-window exceeded.

    Returns:
        (trimmed_messages, was_modified)
    """
    if not messages:
        return messages, False

    # Use a more aggressive target (half the normal)
    target = SNIP_TARGET_TOKENS // 2  # 25K

    result, freed = snip_messages(messages, target_tokens=target)
    was_modified = freed > 0

    if was_modified:
        logger.info("Reactive compact: snipped messages, freed ~%d tokens", freed)

    return result, was_modified


def reactive_compact_on_too_long(
    messages: list[dict],
    max_retries: int = 2,
) -> tuple[list[dict], int]:
    """Iteratively snip and retry on prompt-too-long errors.

    Returns:
        (snipped_messages, total_tokens_freed)
    """
    total_freed = 0

    for attempt in range(max_retries):
        result, freed = snip_messages(
            messages, target_tokens=SNIP_TARGET_TOKENS // (attempt + 1)
        )
        if freed > 0:
            total_freed += freed
            messages = result
        else:
            break  # Can't snip more

    return messages, total_freed
