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
    on_text: Any = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Run the agent loop.

    Args:
        on_progress:  Callback(str) for progress messages.
        on_permission: Callback(tool_name, args) -> bool for user approval.
        on_text:      Callback(str) for incremental text streaming to terminal.
    """
    from general_agent.services.api.messages import query_model_with_streaming

    if tools is None:
        tools = _get_tool_definitions(state.tool_registry)

    assistant_text = ""
    state.turn_count = 0  # Reset per run_agent() call

    # Save the latest user message and remember its UUID for chaining
    _last_user_uuid: str | None = None
    try:
        from general_agent.bootstrap.state import get_session_id, get_original_cwd
        from general_agent.session.store import get_session_store
        _store = get_session_store()
        _sid = get_session_id()
        _cwd = get_original_cwd()
        # Find the last user message added before this run
        user_msgs = [m for m in state.messages if m.get("role") == "user"]
        if user_msgs:
            _last_user_uuid = _store.save_user_message(
                user_msgs[-1], session_id=_sid, cwd=_cwd,
            )
    except Exception:
        pass
    state._memory_turns_since += 1
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
                try:
                    result = await compact_conversation(state.messages, state, is_auto=True)
                    boundary, summary_msgs = build_post_compact_messages(result)
                    state.messages = summary_msgs
                    if on_progress:
                        on_progress(f"  Compressed {result.messages_summarized} msgs "
                                    f"({result.pre_compact_tokens} → ~{result.post_compact_tokens} tokens)")
                    state._compact_tracking.compacted = True
                    continue
                except Exception:
                    # Compact failed (fork API error) → fallback to snip
                    pass
            elif state._compact_tracking.compacted:
                state._compact_tracking.turn_counter += 1
        except Exception:
            pass

        # Emergency snip: at 80%, hard-cut regardless of compact success/failure
        try:
            from general_agent.compact.snip import snip_messages
            from general_agent.compact.constants import estimate_tokens, threshold_from_pct
            emergency = threshold_from_pct(80)
            if estimate_tokens(state.messages) >= emergency:
                state.messages, freed = snip_messages(state.messages)
                if freed > 0 and on_progress:
                    on_progress(f"  ⚡ Emergency snip: freed ~{freed} tokens")
        except Exception:
            pass

        # Snip: regular check at configured threshold
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
        first_token = True
        import time as _time
        _t0 = _time.monotonic()

        try:
            async for msg in query_model_with_streaming(
                messages=list(state.messages),
                system_prompt=system_prompt,
                model=model,
                max_tokens=max_tokens,
                tools=tools,
                signal=state.abort_signal,
            ):
                # Handle raw stream events — extract text deltas for real-time display
                if msg.get("type") == "stream_event":
                    chunk = msg.get("event")
                    text = _extract_delta_text(chunk)
                    if text:
                        if first_token:
                            first_token = False
                        if on_text:
                            on_text(text)
                    continue

                if msg.get("role") == "assistant":
                    state.messages.append(msg)
                    # Repetition detection: prevent stuck infinite loop
                    if _is_repeating(state.messages):
                        logger.warning("Agent repetition detected - breaking loop")
                        state.abort_signal.set()
                    # Save full transcript to disk (cc-haha sessionTranscript)
                    try:
                        from general_agent.bootstrap.state import get_session_id, get_original_cwd
                        from general_agent.session.store import get_session_store
                        _asst_store = get_session_store()
                        _asst_store.save_assistant_message(
                            msg,
                            session_id=get_session_id(),
                            cwd=get_original_cwd(),
                            parent_uuid=_last_user_uuid,
                        )
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
            args_input = block.get("input", {})
            detail = _tool_detail(name, args_input)

            result, tool_display = await _execute_tool(
                block, state.tool_registry, on_permission, state,
            )

            # Show result: success/fail dot + display output
            is_error = result.get("is_error", False)
            if on_progress:
                from general_agent.ui.render import tool_call
                on_progress(tool_call(name, detail, success=not is_error))
                if tool_display:
                    on_progress(tool_display)

            tool_results.append(result)

        # 5. Inject tool_results into conversation
        if tool_results:
            state.messages.append({
                "role": "user",
                "content": tool_results,
            })

    # Max turns reached - force one final response without tools
    if state.abort_signal.is_set():
        return "Agent stopped: repetition detected", state.messages
    try:
        async for msg in query_model_with_streaming(
            messages=list(state.messages),
            system_prompt=await build_system_prompt(
                tools=[],
                git_context=state.git_context,
                extra_instructions=state.system_prompt_extra,
            ),
            model=model,
            tools=[],
            signal=state.abort_signal,
        ):
            if msg.get("role") == "assistant":
                c = msg.get("content", "")
                if isinstance(c, list):
                    for b in c:
                        if b.get("type") == "text":
                            assistant_text = b.get("text", "")
                            break
    except Exception:
        pass
    return assistant_text or "Response truncated (max turns reached)", state.messages


def _is_repeating(messages: list[dict]) -> bool:
    """Detect if the agent is stuck repeating the exact same response.

    Requires 5 consecutive identical assistant responses.
    This is intentionally conservative — false positives harm
    multi-step tool operations.
    """
    assistant_texts = []
    for m in reversed(messages):
        if m.get("role") == "assistant":
            c = m.get("content", "")
            if isinstance(c, list):
                txt = " ".join(b.get("text", "") for b in c if b.get("type") == "text")
            else:
                txt = str(c)
            assistant_texts.append(txt)
            if len(assistant_texts) >= 5:
                break
    if len(assistant_texts) < 5:
        return False
    return len(set(assistant_texts)) == 1


def _extract_delta_text(chunk: Any) -> str:
    """Extract text delta from a stream event chunk.

    Handles both:
      - OpenAI format:  chunk.choices[0].delta.content
      - Anthropic format: chunk.delta.text (content_block_delta / text_delta)
    """
    # OpenAI / OpenAI-compatible format
    if hasattr(chunk, "choices") and chunk.choices:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            return delta.content

    # Anthropic / Anthropic-compatible format
    if hasattr(chunk, "type") and hasattr(chunk, "delta"):
        if chunk.type == "content_block_delta":
            dt = getattr(chunk.delta, "type", "")
            if dt == "text_delta":
                return getattr(chunk.delta, "text", "") or ""

    return ""


def _tool_detail(name: str, args: dict[str, Any]) -> str:
    """Build a detail string for a tool call. Shows the key parameter."""
    if name == "Bash":
        cmd = args.get("command", "")
        from general_agent.tools.bash_ui import format_command_display
        return format_command_display(cmd)
    if name in ("Read", "Glob", "Grep"):
        return args.get("file_path") or args.get("path") or args.get("pattern", "")
    if name in ("Write", "Edit"):
        return args.get("file_path", "")
    if name == "WebFetch":
        return args.get("url", "")[:60]
    if name == "Agent":
        return args.get("description", "")
    return _format_args(args)


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
) -> tuple[dict[str, Any], str]:
    """Execute a single tool call with permission handling.

    Returns:
        (tool_result_block, display_text)
        display_text is user-facing formatted output (e.g. colored/truncated bash output),
        empty string if the tool doesn't provide display formatting.
    """

    name = tool_use.get("name", "")
    tool_id = tool_use.get("id", "")
    args = tool_use.get("input", {})

    tool = registry.get(name)
    if not tool:
        return _tool_error(tool_id, f"Unknown tool: {name}"), ""

    # Validate input
    validation = await tool.validate_input(args)
    if validation is not None:
        return _tool_error(tool_id, f"Validation failed: {validation.get('message', validation)}"), ""

    # Check permissions
    perm = await tool.check_permissions(args)
    if perm.behavior == "deny":
        return _tool_error(tool_id, f"Permission denied: {perm.message}"), ""

    if perm.behavior == "ask":
        if agent_state and getattr(agent_state, "is_fork_agent", False):
            pass  # Fork agent: auto-allow (no terminal for user prompt)
        elif on_permission and on_permission(name, args):
            pass  # User approved
        elif tool.is_read_only(args):
            pass  # Read-only: auto-allow
        else:
            return _tool_error(tool_id, "Operation requires user confirmation but was denied"), ""

    # Execute
    try:
        result = await tool.call(args, context=agent_state)
        block = tool.map_tool_result_to_block(result.data, tool_id)
        # Extract user-facing display text if available
        display = ""
        if isinstance(result.data, dict):
            display = result.data.get("display", "")
        return block, display
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return _tool_error(tool_id, f"Tool error: {e}"), ""


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
