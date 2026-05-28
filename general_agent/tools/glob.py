"""GlobTool - filename pattern matching.

Reference: cc-haha src/tools/GlobTool/GlobTool.ts
"""

from __future__ import annotations

import glob as glob_module
import os
from typing import Any

from general_agent.tools.tool import Tool, ToolResult


class GlobTool(Tool):
    name = "Glob"
    max_result_size_chars = 30_000

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern to match (e.g. **/*.py, src/**/*.ts)"},
                "path": {"type": "string", "description": "Directory to search in (defaults to cwd)"},
            },
            "required": ["pattern"],
        }

    def is_read_only(self, args: dict[str, Any]) -> bool:
        return True

    def is_concurrency_safe(self, args: dict[str, Any]) -> bool:
        return True

    async def description(self, input: dict[str, Any] | None = None) -> str:
        return "Find files matching a glob pattern"

    async def prompt(self) -> str:
        return """Find files matching a glob pattern.

- Use ** for recursive directory search (e.g. src/**/*.py).
- Use ? to match single characters, * to match any sequence.
- Results are sorted by modification time (newest first)."""

    async def validate_input(
        self, args: dict[str, Any], context: Any = None
    ) -> dict | None:
        pattern = args.get("pattern", "").strip()
        if not pattern:
            return {"result": False, "message": "pattern is required"}
        return None

    async def call(self, args: dict[str, Any], context=None, **kw) -> ToolResult:
        pattern = args["pattern"]
        search_path = args.get("path") or os.getcwd()

        full_pattern = os.path.join(search_path, pattern)
        try:
            matches = glob_module.glob(full_pattern, recursive=True)
            # Sort by mtime, newest first
            matches = sorted(matches, key=lambda f: os.path.getmtime(f), reverse=True)

            # Truncate if too many
            if len(matches) > 500:
                output = "\n".join(matches[:500])
                output += f"\n... ({len(matches) - 500} more files)"
            else:
                output = "\n".join(matches) if matches else "(no matches)"

            return ToolResult(data={
                "output": output,
                "count": len(matches),
                "truncated": len(matches) > 500,
            })
        except Exception as e:
            return ToolResult(data={"output": f"Error: {e}", "count": 0})

    def map_tool_result_to_block(self, output: Any, tool_use_id: str) -> dict:
        text = output.get("output", str(output)) if isinstance(output, dict) else str(output)
        return {"type": "tool_result", "tool_use_id": tool_use_id, "content": text, "is_error": False}
