"""System prompt assembly - matches cc-haha prompt construction pattern.

Builds the system prompt from: base instructions + tool descriptions + git context.
"""

from __future__ import annotations

import asyncio

BASE_SYSTEM_PROMPT = """You are a general-purpose AI agent. Your task is to help the user with
software engineering and general problem-solving tasks.

You have access to tools for reading/writing files and executing commands.
Use tools when needed, and respond with text otherwise.

IMPORTANT:
- When reading files, use the Read tool with the exact file path.
- When editing files, use the Edit tool with old_string/new_string for precise changes.
- When writing new files, use the Write tool.
- When running commands, use the Bash tool.
- Always validate tool inputs before calling.
- If a tool call fails, read the error and adjust your approach.
"""


async def build_system_prompt(
    tools: list,
    git_context: str = "",
    extra_instructions: str = "",
) -> str:
    """Assemble the system prompt from all sources (async for tool prompts)."""
    parts = [BASE_SYSTEM_PROMPT]

    if tools:
        parts.append("\n## Available Tools\n")
        for tool in tools:
            if not tool.is_enabled():
                continue
            prompt_text = await _get_tool_prompt(tool)
            parts.append(prompt_text)
            parts.append("")

    if git_context:
        parts.append(git_context)

    if extra_instructions:
        parts.append(extra_instructions)

    return "\n".join(parts)


async def _get_tool_prompt(tool) -> str:
    """Get tool description text with caching."""
    if hasattr(tool, "_cached_prompt") and tool._cached_prompt:
        return tool._cached_prompt

    try:
        desc = await tool.prompt()
    except Exception:
        desc = ""

    text = desc or tool.name
    schema = tool.get_input_schema()
    props = ", ".join(schema.get("properties", {}).keys()) if schema.get("properties") else ""

    prompt = f"### {tool.name}"
    if props:
        prompt += f" ({props})"
    prompt += f"\n  {text}\n"
    tool._cached_prompt = prompt
    return prompt
