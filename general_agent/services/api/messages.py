"""Core API query - provider dispatch (OpenAI or Anthropic).

query_model() yields stream events + assembled messages.
Non-streaming wrapper returns a single dict.

Provider selection: reads GENERAL_AGENT_PROVIDER from env.
  "anthropic" → Anthropic Messages API (DeepSeek /anthropic endpoint)
  default     → OpenAI Chat Completions (DeepSeek /v1 endpoint)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, AsyncGenerator

from general_agent.constants.models import DEFAULT_MODEL

logger = logging.getLogger("general_agent.api")


def _get_provider() -> str:
    return os.environ.get("GENERAL_AGENT_PROVIDER", "openai")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def query_model_without_streaming(
    messages: list[dict[str, Any]],
    system_prompt: str | None = None,
    *,
    model: str = "",
    max_tokens: int = 4096,
    temperature: float | None = 0.7,
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Non-streaming query. Dispatches to provider-specific implementation."""
    if not model:
        model = os.environ.get("GENERAL_AGENT_MODEL", DEFAULT_MODEL)

    if _get_provider() == "anthropic":
        from general_agent.services.api.messages_anthropic import (
            query_model_without_streaming_anthropic,
        )
        return await query_model_without_streaming_anthropic(
            messages=messages, system_prompt=system_prompt,
            model=model, max_tokens=max_tokens,
            temperature=temperature, tools=tools,
        )

    # OpenAI-compatible path
    api_messages = _build_api_messages(messages, system_prompt)

    params: dict[str, Any] = {
        "model": model,
        "messages": api_messages,
        "max_tokens": max_tokens,
        "temperature": temperature or 0.7,
        "stream": False,
    }
    if tools:
        params["tools"] = tools

    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

    start = time.monotonic()
    response = client.chat.completions.create(**params)
    duration_ms = int((time.monotonic() - start) * 1000)

    choice = response.choices[0]
    msg = choice.message

    content_blocks = [{"type": "text", "text": msg.content or ""}]
    if msg.tool_calls:
        for tc in msg.tool_calls:
            content_blocks.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": _safe_json_parse(tc.function.arguments),
            })

    return {
        "role": "assistant",
        "content": content_blocks,
        "stop_reason": choice.finish_reason,
        "usage": _usage_dict(response.usage, duration_ms, model, params.get("model", model)),
    }


async def query_model_with_streaming(
    messages: list[dict[str, Any]],
    system_prompt: str | None = None,
    *,
    model: str = "",
    max_tokens: int = 4096,
    temperature: float | None = 0.7,
    tools: list[dict[str, Any]] | None = None,
    signal: asyncio.Event | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Streaming query. Dispatches to provider-specific implementation."""
    if not model:
        model = os.environ.get("GENERAL_AGENT_MODEL", DEFAULT_MODEL)

    if _get_provider() == "anthropic":
        async for entry in _query_anthropic(
            messages=messages, system_prompt=system_prompt,
            model=model, max_tokens=max_tokens,
            temperature=temperature, tools=tools, signal=signal,
        ):
            yield entry
        return

    async for entry in _query_openai(
        messages=messages, system_prompt=system_prompt,
        model=model, max_tokens=max_tokens,
        temperature=temperature, tools=tools, signal=signal,
    ):
        yield entry


async def _query_anthropic(
    messages: list[dict[str, Any]],
    system_prompt: str | None = None,
    *,
    model: str = "",
    max_tokens: int = 4096,
    temperature: float | None = None,
    tools: list[dict[str, Any]] | None = None,
    signal: asyncio.Event | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Delegate to Anthropic SDK (DeepSeek /anthropic endpoint)."""
    from general_agent.services.api.messages_anthropic import query_model_anthropic
    async for entry in query_model_anthropic(
        messages=messages, system_prompt=system_prompt,
        model=model, max_tokens=max_tokens,
        temperature=temperature, tools=tools, signal=signal,
    ):
        yield entry


async def _query_openai(
    messages: list[dict[str, Any]],
    system_prompt: str | None = None,
    *,
    model: str = "",
    max_tokens: int = 4096,
    temperature: float | None = 0.7,
    tools: list[dict[str, Any]] | None = None,
    signal: asyncio.Event | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Core streaming query - async generator.

    Yields:
        dict with type="stream_event" / role="assistant" / type="system_error"
    """
    if not model:
        model = os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL)

    api_messages = _build_api_messages(messages, system_prompt)

    params: dict[str, Any] = {
        "model": model,
        "messages": api_messages,
        "max_tokens": max_tokens,
        "temperature": temperature or 0.7,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        params["tools"] = tools

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

    start = time.monotonic()
    accumulated_text = ""
    accumulated_tool_calls: dict[int, dict[str, Any]] = {}
    finish_reason = "stop"
    usage_info: dict[str, int] | None = None
    ttfb_set = False

    try:
        stream = await client.chat.completions.create(**params)

        async for chunk in stream:
            if signal and signal.is_set():
                break

            # TTFB
            if not ttfb_set:
                ttfb_ms = (time.monotonic() - start) * 1000
                ttfb_set = True
                logger.debug("TTFB: %.0fms", ttfb_ms)

            # Yield raw chunk for streaming consumers
            yield {"type": "stream_event", "event": chunk}

            if chunk.choices:
                delta = chunk.choices[0].delta
                if delta.content:
                    accumulated_text += delta.content
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.id or "",
                                "name": "",
                                "arguments": "",
                            }
                        if tc.id:
                            accumulated_tool_calls[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            accumulated_tool_calls[idx]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            accumulated_tool_calls[idx]["arguments"] += tc.function.arguments

                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason

            # Usage in final chunk (with stream_options)
            if chunk.usage:
                usage_info = {
                    "input_tokens": chunk.usage.prompt_tokens or 0,
                    "output_tokens": chunk.usage.completion_tokens or 0,
                }

        # Assemble final message
        content_blocks: list[dict[str, Any]] = []
        if accumulated_text:
            content_blocks.append({"type": "text", "text": accumulated_text})

        for tc in sorted(accumulated_tool_calls.values(), key=lambda x: int(x.get("index", 0)) if "index" in x else 0):
            content_blocks.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["name"],
                "input": _safe_json_parse(tc["arguments"]),
            })

        duration_ms = int((time.monotonic() - start) * 1000)

        if usage_info:
            _log_usage(model, usage_info, duration_ms, ttfb_ms)

        yield {
            "role": "assistant",
            "content": content_blocks,
            "stop_reason": finish_reason,
            "usage": _usage_dict_raw(usage_info) if usage_info else {},
        }

    except Exception as e:
        logger.warning("Streaming failed (%s)", type(e).__name__)
        # Fallback to non-streaming
        result = await query_model_without_streaming(
            messages=messages,
            system_prompt=system_prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )
        yield result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_api_messages(
    messages: list[dict[str, Any]],
    system_prompt: str | None,
) -> list[dict[str, Any]]:
    """Convert internal messages to OpenAI chat completion format."""
    result: list[dict[str, Any]] = []

    if system_prompt:
        result.append({"role": "system", "content": system_prompt})

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, str):
            result.append({"role": role, "content": content})
        elif isinstance(content, list):
            # Extract text from content blocks
            text_parts = []
            tool_calls = []
            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    tool_calls.append(block)
                elif block.get("type") == "tool_result":
                    result.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": block.get("content", ""),
                    })

            if role == "assistant":
                entry: dict[str, Any] = {"role": "assistant"}
                if text_parts:
                    entry["content"] = "\n".join(text_parts)
                else:
                    entry["content"] = None
                if tool_calls:
                    entry["tool_calls"] = [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": _safe_json_dumps(tc.get("input", {})),
                            },
                        }
                        for tc in tool_calls
                    ]
                result.append(entry)
            else:
                result.append({"role": role, "content": "\n".join(text_parts)})

    return result


def _safe_json_parse(text: str) -> dict[str, Any]:
    import json
    try:
        return json.loads(text) if text else {}
    except json.JSONDecodeError:
        return {}


def _safe_json_dumps(obj: dict[str, Any]) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


def _usage_dict(usage, duration_ms: int, model: str, resolved_model: str) -> dict[str, Any]:
    return {
        "input_tokens": usage.prompt_tokens or 0,
        "output_tokens": usage.completion_tokens or 0,
        "duration_ms": duration_ms,
        "model": model,
        "resolved_model": resolved_model,
    }


def _usage_dict_raw(usage: dict[str, int] | None) -> dict[str, Any]:
    if not usage:
        return {}
    return {"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0)}


def _log_usage(model: str, usage: dict[str, int], duration_ms: int, ttfb_ms: float) -> None:
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    logger.info(
        "API call complete: model=%s input=%d output=%d duration=%dms ttfb=%.0fms",
        model, inp, out, duration_ms, ttfb_ms,
    )
    from general_agent.bootstrap.state import add_to_total_api_duration, add_to_total_cost_usd
    add_to_total_api_duration(duration_ms)
    # DeepSeek pricing: ~$0.27/1M input, ~$1.10/1M output
    cost = (inp / 1_000_000) * 0.27 + (out / 1_000_000) * 1.10
    add_to_total_cost_usd(cost)
