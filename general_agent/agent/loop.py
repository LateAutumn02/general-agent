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
    memory_store: Any = None  # MemoryStore for auto-extraction
    auto_memory: bool = True  # Enable auto-extraction
    _memory_extracted: bool = field(default=False, repr=False)  # Track extraction state


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

    while state.turn_count < state.max_turns:
        if state.abort_signal.is_set():
            break

        state.turn_count += 1

        # 1. Build system prompt
        system_prompt = await build_system_prompt(
            tools=list(state.tool_registry.get_enabled()),
            git_context=state.git_context,
            extra_instructions=state.system_prompt_extra,
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
                    content = msg.get("content", [])
                    for block in content if isinstance(content, list) else []:
                        if block.get("type") == "text":
                            assistant_text += block.get("text", "")
                        elif block.get("type") == "tool_use":
                            tool_use_blocks.append(block)
        except Exception as e:
            logger.error("API call failed (turn %d): %s", state.turn_count, e)
            if state.turn_count < state.max_turns:
                # Retry next turn
                await asyncio.sleep(1)
                continue
            return f"Error after {state.turn_count} retries: {e}", state.messages

        # 3. If no tool_use blocks → handle auto-memory then return
        if not tool_use_blocks:
            # Auto-memory extraction: ask agent to review and save memories
            if (state.memory_store and state.auto_memory
                    and not state._memory_extracted
                    and state.turn_count > 1):
                state._memory_extracted = True
                prompt = state.memory_store.build_extraction_prompt()
                state.messages.append({"role": "user", "content": prompt})
                continue  # Let agent handle extraction, then finish
            return assistant_text, state.messages

        # 4. Execute tools
        tool_results = []
        for block in tool_use_blocks:
            name = block.get("name", "?")
            args_preview = _format_args(block.get("input", {}))
            if on_progress:
                on_progress(f"  \033[33m→\033[0m {name} {args_preview}")
            result = await _execute_tool(block, state.tool_registry, on_permission)
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
    for key in ("command", "file_path", "old_string"):
        if key in args:
            val = str(args[key])
            if len(val) > 60:
                val = val[:57] + "..."
            return val
    # Fallback: show first arg
    items = list(args.items())[:2]
    text = " ".join(f"{k}={str(v)[:20]}" for k, v in items)
    return text[:80]


async def _execute_tool(
    tool_use: dict[str, Any],
    registry: ToolsRegistry,
    on_permission: Any = None,
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
        if on_permission and on_permission(name, args):
            pass  # User approved
        elif tool.is_read_only(args):
            pass  # Read-only: auto-allow
        else:
            return _tool_error(tool_id, "Operation requires user confirmation but was denied")

    # Execute
    try:
        result = await tool.call(args)
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
