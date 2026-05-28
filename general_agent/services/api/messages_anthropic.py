"""Anthropic API format client (for DeepSeek /anthropic endpoint).

Uses Anthropic SDK with custom base_url.
Works with any Anthropic-compatible API (DeepSeek, Anthropic, etc.).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, AsyncGenerator

logger = logging.getLogger("general_agent.api.anthropic")


async def query_model_anthropic(
    messages: list[dict[str, Any]],
    system_prompt: str | None = None,
    *,
    model: str = "deepseek-v4-pro",
    max_tokens: int = 4096,
    temperature: float | None = None,
    tools: list[dict[str, Any]] | None = None,
    signal: asyncio.Event | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Streaming query using Anthropic Messages API.

    Works with DeepSeek's /anthropic endpoint or native Anthropic API.
    """
    from anthropic import AsyncAnthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

    # Build system prompt as content blocks
    system_blocks: list[dict[str, Any]] = []
    if system_prompt:
        system_blocks.append({"type": "text", "text": system_prompt})

    # Build Anthropic-format messages
    anthropic_messages = _to_anthropic_messages(messages)

    params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": anthropic_messages,
    }
    if system_blocks:
        params["system"] = system_blocks
    if tools:
        params["tools"] = _to_anthropic_tools(tools)

    # Anthropic requires temperature or thinking, not both
    if temperature is not None:
        params["temperature"] = temperature

    client = AsyncAnthropic(
        api_key=api_key,
        base_url=base_url,
        max_retries=0,
    )

    start = time.monotonic()
    accumulated_text = ""
    accumulated_tool_uses: dict[str, dict[str, Any]] = {}
    finish_reason = "end_turn"
    usage_info: dict[str, int] = {}
    ttfb_set = False
    last_yielded: dict[str, Any] | None = None

    try:
        async with client.beta.messages.stream(**params) as stream:
            async for event in stream:
                if signal and signal.is_set():
                    break

                if not ttfb_set:
                    ttfb_set = True
                    logger.debug("TTFB: %.0fms", (time.monotonic() - start) * 1000)

                yield {"type": "stream_event", "event": event}

                event_type = getattr(event, "type", "")

                if event_type == "content_block_delta":
                    delta = event.delta
                    delta_type = getattr(delta, "type", "")
                    if delta_type == "text_delta":
                        accumulated_text += getattr(delta, "text", "")
                    elif delta_type == "input_json_delta":
                        pass  # Accumulated via tool_use blocks

                elif event_type == "content_block_stop":
                    # Not used - we assemble at message_delta
                    pass

                elif event_type == "message_delta":
                    delta = getattr(event, "delta", None)
                    if delta:
                        finish_reason = getattr(delta, "stop_reason", "end_turn")
                    usage = getattr(event, "usage", None)
                    if usage:
                        usage_info = {
                            "input_tokens": getattr(usage, "input_tokens", 0) or 0,
                            "output_tokens": getattr(usage, "output_tokens", 0) or 0,
                        }

    except Exception as e:
        logger.error("Anthropic streaming failed: %s", e)
        raise
    finally:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "Anthropic API: model=%s input=%d output=%d duration=%dms ttfb=%.0fms",
            model,
            usage_info.get("input_tokens", 0),
            usage_info.get("output_tokens", 0),
            duration_ms,
            ttfb_set and (time.monotonic() - start) * 1000 - duration_ms or 0,
        )

    # Assemble and yield final message
    content_blocks: list[dict[str, Any]] = []
    if accumulated_text:
        content_blocks.append({"type": "text", "text": accumulated_text})

    yield {
        "role": "assistant",
        "content": content_blocks,
        "stop_reason": finish_reason,
        "usage": usage_info,
    }

    from general_agent.bootstrap.state import add_to_total_api_duration, add_to_total_cost_usd
    add_to_total_api_duration(duration_ms)
    inp = usage_info.get("input_tokens", 0)
    out = usage_info.get("output_tokens", 0)
    cost = (inp / 1_000_000) * 0.27 + (out / 1_000_000) * 1.10
    add_to_total_cost_usd(cost)


async def query_model_without_streaming_anthropic(
    messages: list[dict[str, Any]],
    system_prompt: str | None = None,
    *,
    model: str = "deepseek-v4-pro",
    max_tokens: int = 4096,
    temperature: float | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Non-streaming Anthropic query. Returns single AssistantMessage."""
    result: dict[str, Any] = {"role": "assistant", "content": "", "usage": {}}
    async for msg in query_model_anthropic(
        messages=messages,
        system_prompt=system_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        tools=tools,
    ):
        if msg.get("role") == "assistant":
            result = msg
    return result


# ---------------------------------------------------------------------------
# Format conversion
# ---------------------------------------------------------------------------


def _to_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert internal messages to Anthropic API format."""
    result: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, str):
            result.append({"role": role, "content": content})
        elif isinstance(content, list):
            blocks: list[dict[str, Any]] = []
            tool_results: list[dict[str, Any]] = []

            for block in content:
                block_type = block.get("type", "text")
                if block_type == "text":
                    blocks.append({"type": "text", "text": block.get("text", "")})
                elif block_type == "tool_use":
                    blocks.append({
                        "type": "tool_use",
                        "id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "input": block.get("input", {}),
                    })
                elif block_type == "tool_result":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.get("tool_use_id", ""),
                        "content": block.get("content", ""),
                        "is_error": block.get("is_error", False),
                    })

            if role == "assistant":
                result.append({"role": "assistant", "content": blocks})
            elif tool_results:
                result.append({"role": "user", "content": tool_results})
            else:
                result.append({"role": "user", "content": blocks})

    return result


def _to_anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI-format tools to Anthropic format."""
    result: list[dict[str, Any]] = []
    for tool in tools:
        if tool.get("type") == "function":
            func = tool["function"]
            result.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            })
        else:
            result.append(tool)
    return result
