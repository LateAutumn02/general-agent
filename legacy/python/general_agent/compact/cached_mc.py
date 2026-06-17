"""Cached microcompact stub - API cache-control based compaction.

Matching cc-haha cachedMicrocompact.ts pattern.
Uses Anthropic cache_edits API to delete KV cache entries.
DeepSeek currently doesn't support this API - stub for future.
"""


def is_cached_mc_enabled() -> bool:
    """Check if cached microcompact (cache_edits API) is available."""
    return False  # Stub: requires Anthropic cache_edits API


async def cached_microcompact(messages: list[dict]) -> list[dict]:
    """Stub: use cache_edits API to delete cached content blocks.

    Not yet implemented - requires Anthropic-specific cache_edits API support.
    DeepSeek /anthropic endpoint may support this in future.
    """
    # TODO: Implement when cache_edits API is available
    return messages
