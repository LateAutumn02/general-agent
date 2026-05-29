"""Agent core loop - while True pattern matching cc-haha query.ts.

Flow:
  while True:
    1. Build system prompt
    2. Call API (streaming)
    3. If no tool_use blocks → return result
    4. Execute tools → inject tool_result → continue

Reference: cc-haha src/query.ts, docs/agent/flow.md
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from general_agent.agent.prompt import build_system_prompt
from general_agent.tools.registry import ToolsRegistry

logger = logging.getLogger("general_agent.agent")


@dataclass
class AgentState:
    """Mutable state carried across loop iterations."""
    messages: list[dict[str, Any]] = field(default_factory=list)
    turn_count: int = 0
    max_turns: int = 100
    tool_registry: ToolsRegistry = field(default_factory=ToolsRegistry)
    abort_signal: asyncio.Event = field(default_factory=asyncio.Event)
    system_prompt_extra: str = ""
    git_context: str = ""
    memory_store: Any = None
    auto_memory: bool = True
    memory_interval: int = 3
    is_fork_agent: bool = False
    compact_pct: int = 50  # Auto-compact at 50% of context window
    snip_pct: int = 80  # Snip at 80% of context window
    _memory_extracted: bool = field(default=False, repr=False)
    _memory_turns_since: int = field(default=0, repr=False)


async def run_agent(
    state: AgentState,
    *,
    model: str = "",
    max_tokens: int = 4096,
    tools: list | None = None,
    on_progress: Any = None,
    on_permission: Any = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Run the agent loop.

    Args:
        on_progress: Callback(str) for progress messages.
        on_permission: Callback(tool_name, args) -> bool for user approval.
    """
    from general_agent.services.api.messages import query_model_with_streaming

    if tools is None:
        tools = _get_tool_definitions(state.tool_registry)

    assistant_text = ""
    state._memory_turns_since += 1  # Count each run_agent() call (cc-haha: per-query)
    while state.turn_count < state.max_turns:
        if state.abort_signal.is_set():
            break

        state.turn_count += 1

        # 0. Pre-API compaction chain (truncate → microcompact → autoCompact → snip)
        try:
            from general_agent.compact.micro_compact import microcompact, truncate_large_results
            truncate_large_results(state.messages)
            state.messages = microcompact(state.messages)
        except Exception:
            pass

        try:
            from general_agent.compact.compact import (
                compact_conversation,
                build_post_compact_messages,
                should_auto_compact,
            )
            from general_agent.compact.state import AutoCompactTrackingState

            if not hasattr(state, "_compact_tracking"):
                state._compact_tracking = AutoCompactTrackingState()

            if await should_auto_compact(
                state.messages, model=model, tracking=state._compact_tracking,
                pct=state.compact_pct,
            ):
                result = await compact_conversation(state.messages, state, is_auto=True)
                boundary, summary_msgs = build_post_compact_messages(result)
                state.messages = summary_msgs
                if on_progress:
                    on_progress(f"  Compressed {result.messages_summarized} messages "
                                f"({result.pre_compact_tokens} → ~{result.post_compact_tokens} tokens)")
                state._compact_tracking.compacted = True
                continue
            elif state._compact_tracking.compacted:
                state._compact_tracking.turn_counter += 1
        except Exception:
            pass

        # Snip: fallback when auto-compact not applicable (cheap, but lossy)
        try:
            from general_agent.compact.snip import try_snip
            state.messages, _ = try_snip(state.messages, model=model, pct=state.snip_pct)
        except Exception:
            pass

        # 1. Build system prompt with relevant memories
        # Per-query: select up to 5 relevant memories (cc-haha pattern)
        memory_extra = state.system_prompt_extra
        if state.memory_store and state.auto_memory:
            user_msg = ""
            for m in reversed(state.messages):
                if m.get("role") == "user":
                    c = m.get("content", "")
                    user_msg = c if isinstance(c, str) else ""
                    break
            if user_msg:
                try:
                    relevant = await state.memory_store.find_relevant(user_msg)
                    if relevant:
                        memory_extra = state.memory_store.format_relevant(relevant)
                except Exception:
                    pass

        system_prompt = await build_system_prompt(
            tools=list(state.tool_registry.get_enabled()),
            git_context=state.git_context,
            extra_instructions=memory_extra,
        )

        # 2. Call API
        tool_use_blocks: list[dict[str, Any]] = []
        assistant_text = ""

        try:
            async for msg in query_model_with_streaming(
                messages=list(state.messages),
                system_prompt=system_prompt,
                model=model,
                max_tokens=max_tokens,
                tools=tools,
                signal=state.abort_signal,
            ):
                if msg.get("role") == "assistant":
                    state.messages.append(msg)
                    # Save full transcript to disk (cc-haha sessionTranscript)
                    try:
                        from general_agent.compact.transcript import save_transcript
                        save_transcript([msg])
                    except Exception:
                        pass
                    content = msg.get("content", [])
                    for block in content if isinstance(content, list) else []:
                        if block.get("type") == "text":
                            assistant_text += block.get("text", "")
                        elif block.get("type") == "tool_use":
                            tool_use_blocks.append(block)
        except Exception as e:
            err_str = str(e).lower()
            # Reactive compact: if prompt too long (413), snip and retry
            if any(kw in err_str for kw in ("prompt", "too long", "413", "context_window_exceeded")):
                from general_agent.compact.reactive import try_reactive_compact
                state.messages, freed = try_reactive_compact(state.messages)
                if freed > 0 and state.turn_count < state.max_turns:
                    logger.info("Reactive compact: freed ~%d tokens, retrying", freed)
                    await asyncio.sleep(1)
                    continue

            logger.error("API call failed (turn %d): %s", state.turn_count, e)
            if state.turn_count < state.max_turns:
                await asyncio.sleep(1)
                continue
            return f"Error after {state.turn_count} retries: {e}", state.messages

        # 3. If no tool_use blocks → handle auto-memory then return
        if not tool_use_blocks:
            # Save user-facing answer before extraction overwrites it
            save_answer = assistant_text
            # Auto-memory extraction via fork agent (cc-haha pattern)
            if (state.memory_store and state.auto_memory
                    and state._memory_turns_since >= state.memory_interval):
                state._memory_turns_since = 0
                from general_agent.tasks.fork import create_fork_context, run_forked_agent
                fork_ctx = create_fork_context(state, agent_id="memory-extract", max_turns=5)
                prompt = state.memory_store.build_extraction_prompt()
                task = asyncio.create_task(
                    run_forked_agent(fork_ctx, prompt)
                )
                task.add_done_callback(
                    lambda t: logger.error("Fork extraction failed: %s", t.exception())
                    if t.exception() else None
                )
            return save_answer, state.messages

        # 4. Execute tools
        tool_results = []
        for block in tool_use_blocks:
            name = block.get("name", "?")
            args_preview = _format_args(block.get("input", {}))
            if on_progress:
                on_progress(f"  \033[33m→\033[0m {name} {args_preview}")
            result = await _execute_tool(block, state.tool_registry, on_permission, state)
            tool_results.append(result)

        # 5. Inject tool_results into conversation
        if tool_results:
            state.messages.append({
                "role": "user",
                "content": tool_results,
            })

    # Max turns reached
    return assistant_text or "(Agent stopped - max turns reached)", state.messages


def _format_args(args: dict[str, Any]) -> str:
    """Format tool arguments for display (max 80 chars)."""
    if not args:
        return ""
    # Show file_path or command as the key arg
    for key in ("command", "file_path", "old_string", "description", "prompt"):
        if key in args:
            val = str(args[key])
            if len(val) > 60:
                val = val[:57] + "..."
            return val
    # Fallback: show first args
    items = list(args.items())[:2]
    parts = []
    for k, v in items:
        s = str(v)
        parts.append(f"{k}={s[:40] + '...' if len(s) > 40 else s}")
    text = " ".join(parts)
    return text[:80] + ("..." if len(text) > 80 else "")


async def _execute_tool(
    tool_use: dict[str, Any],
    registry: ToolsRegistry,
    on_permission: Any = None,
    agent_state: Any = None,
) -> dict[str, Any]:
    """Execute a single tool call with permission handling."""

    name = tool_use.get("name", "")
    tool_id = tool_use.get("id", "")
    args = tool_use.get("input", {})

    tool = registry.get(name)
    if not tool:
        return _tool_error(tool_id, f"Unknown tool: {name}")

    # Validate input
    validation = await tool.validate_input(args)
    if validation is not None:
        return _tool_error(tool_id, f"Validation failed: {validation.get('message', validation)}")

    # Check permissions
    perm = await tool.check_permissions(args)
    if perm.behavior == "deny":
        return _tool_error(tool_id, f"Permission denied: {perm.message}")

    if perm.behavior == "ask":
        if agent_state and getattr(agent_state, "is_fork_agent", False):
            pass  # Fork agent: auto-allow (no terminal for user prompt)
        elif on_permission and on_permission(name, args):
            pass  # User approved
        elif tool.is_read_only(args):
            pass  # Read-only: auto-allow
        else:
            return _tool_error(tool_id, "Operation requires user confirmation but was denied")

    # Execute
    try:
        result = await tool.call(args, context=agent_state)
        return tool.map_tool_result_to_block(result.data, tool_id)
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return _tool_error(tool_id, f"Tool error: {e}")


def _tool_error(tool_use_id: str, message: str) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": message,
        "is_error": True,
    }


def _get_tool_definitions(registry: ToolsRegistry) -> list[dict[str, Any]]:
    """Generate API-compatible tool definitions from registry."""
    definitions = []
    for tool in registry.get_enabled():
        schema = tool.get_input_schema()
        definitions.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.name,
                "parameters": schema,
            },
        })
    return definitions
