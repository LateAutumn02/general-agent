"""Microcompact - clears old tool results to free context.

Matching cc-haha microCompact.ts pattern.
Works by modifying messages in-place (clearing old tool_result content).
"""

CLEARED_MESSAGE = "[Old tool result content cleared]"

# Tools whose results can be compacted (matching cc-haha COMPACTABLE_TOOLS)
COMPACTABLE_TOOLS = ("Bash", "Read", "Grep", "Glob", "WebFetch", "Write", "Edit")

# Number of recent tool results to keep
KEEP_RECENT = 5


def microcompact(messages: list[dict], keep_recent: int = KEEP_RECENT) -> list[dict]:
    """Clear old tool_result content, keeping the most recent N results.

    Works on the message list in-place. Returns the list for chaining.
    No API calls needed - this is a pure data operation.
    """
    result_indices = []
    for i, msg in enumerate(messages):
        content = msg.get("content", "")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    result_indices.append(i)
                    break

    # Keep the last N tool_result messages, clear older ones
    to_clear = result_indices[:-keep_recent] if len(result_indices) > keep_recent else []

    for i in to_clear:
        content = messages[i].get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    block["content"] = CLEARED_MESSAGE

    return messages


MAX_TOOL_RESULT_CHARS = 10_000
HEAD_CHARS = 3_000
TAIL_CHARS = 3_000


def truncate_large_results(messages: list[dict], max_chars: int = MAX_TOOL_RESULT_CHARS) -> list[dict]:
    """Truncate individual tool_result content - keep head and tail, cut middle.

    Matching cc-haha content replacement / budget pruning pattern.
    Preserves context: first 3K + last 3K, with the omitted count in between.
    """
    for msg in messages:
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    text = block.get("content", "")
                    if isinstance(text, str) and len(text) > max_chars:
                        omitted = len(text) - HEAD_CHARS - TAIL_CHARS
                        block["content"] = (
                            text[:HEAD_CHARS]
                            + f"\n... ({omitted} chars omitted, full transcript saved to disk) ...\n"
                            + text[-TAIL_CHARS:]
                        )
