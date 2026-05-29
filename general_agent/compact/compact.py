"""Auto/manual compact - generates a structured summary via fork agent.

Matching cc-haha compact.ts pattern:
  compactConversation() -> fork agent -> CompactionResult
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from general_agent.compact.constants import (
    MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES,
    MAX_OUTPUT_TOKENS_FOR_SUMMARY,
    estimate_tokens,
    get_auto_compact_threshold,
)
from general_agent.compact.prompts import format_compact_summary, get_compact_prompt
from general_agent.compact.state import (
    AutoCompactTrackingState,
    CompactionResult,
    TokenWarningState,
)
from general_agent.compact.micro_compact import microcompact

logger = logging.getLogger("general_agent.compact")


async def should_auto_compact(
    messages: list[dict],
    model: str = "",
    tracking: AutoCompactTrackingState | None = None,
    pct: int = 91,
) -> bool:
    """Check if auto-compact should trigger."""
    if tracking and tracking.consecutive_failures >= MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES:
        return False

    from general_agent.compact.constants import threshold_from_pct

    tokens = estimate_tokens(messages)
    threshold = threshold_from_pct(pct)
    return tokens >= threshold


def calculate_warning_state(messages: list[dict], model: str = "") -> TokenWarningState:
    """Calculate token usage relative to thresholds."""
    from general_agent.compact.constants import (
        get_auto_compact_threshold,
        get_effective_context_window_size,
        get_warning_threshold,
        MANUAL_COMPACT_BUFFER_TOKENS,
    )

    tokens = estimate_tokens(messages)
    threshold = get_auto_compact_threshold(model)
    warning = get_warning_threshold(model)
    blocking = get_effective_context_window_size(model) - MANUAL_COMPACT_BUFFER_TOKENS
    pct = max(0, int((1 - tokens / threshold) * 100)) if threshold > 0 else 100

    return TokenWarningState(
        current_tokens=tokens,
        threshold=threshold,
        is_above_warning=tokens >= warning,
        is_above_compact=tokens >= threshold,
        is_at_blocking=tokens >= blocking,
        percent_left=pct,
    )


async def compact_conversation(
    messages: list[dict],
    state: Any,
    *,
    is_auto: bool = True,
    custom_instructions: str = "",
) -> CompactionResult:
    """Generate a compact summary via fork agent.

    Matching cc-haha compactConversation pattern:
    1. Count pre-compact tokens
    2. Build compact prompt (NO_TOOLS + 9 sections)
    3. Run fork agent to generate summary
    4. Format and return result
    """
    from general_agent.tasks.fork import create_fork_context, run_forked_agent

    pre_tokens = estimate_tokens(messages)
    prompt = get_compact_prompt(custom_instructions)

    fork_ctx = create_fork_context(state, agent_id="compact-summary", max_turns=3)
    fork_ctx.parent_messages = list(messages)

    try:
        result_text, _ = await asyncio.wait_for(
            run_forked_agent(fork_ctx, prompt), timeout=60
        )
        summary = format_compact_summary(result_text)

        return CompactionResult(
            summary_text=summary,
            pre_compact_tokens=pre_tokens,
            post_compact_tokens=estimate_tokens([{"role": "user", "content": summary}]),
            messages_summarized=len(messages),
        )
    except Exception as e:
        logger.error("Compact failed: %s", e)
        raise


def build_post_compact_messages(
    result: CompactionResult,
    recent_messages: list[dict] | None = None,
) -> tuple[dict, list[dict]]:
    """Build the boundary marker + summary messages for the compacted conversation.

    Returns (boundary_message, summary_messages).
    """
    from general_agent.compact.state import SystemCompactBoundaryMessage

    boundary = {
        "role": "system",
        "subtype": "compact_boundary",
        "content": f"Conversation compacted. {result.messages_summarized} messages summarized "
                   f"({result.pre_compact_tokens} → ~{result.post_compact_tokens} tokens).",
    }

    summary_wrapper = (
        f"This session is being continued from a previous conversation "
        f"that ran out of context. The summary below covers the earlier "
        f"portion of the conversation. If you need specific details, "
        f"read the full transcript or use the Read tool.\n\n"
        f"{result.summary_text}\n\n"
        f"Continue the conversation from where it left off without "
        f"asking the user any further questions. Resume directly."
    )

    return boundary, [{"role": "user", "content": summary_wrapper}]
