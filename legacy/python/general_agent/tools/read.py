"""FileReadTool - read file contents.

Reference: cc-haha src/tools/FileReadTool/FileReadTool.ts
"""

from __future__ import annotations

import os
from typing import Any

from general_agent.tools.tool import PermissionResult, Tool, ToolResult

READ_TOOL_PROMPT = """Read a file from the local filesystem.

- Supports text files and images (PNG, JPG).
- Use `offset` and `limit` to read specific sections of large files.
- Reading the same file multiple times is fine - the tool caches reads."""


class FileReadTool(Tool):
    name = "Read"
    max_result_size_chars = 100_000

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to read"},
                "offset": {"type": "integer", "description": "Line number to start reading from"},
                "limit": {"type": "integer", "description": "Number of lines to read"},
            },
            "required": ["file_path"],
        }

    def is_read_only(self, args: dict[str, Any]) -> bool:
        return True

    def is_concurrency_safe(self, args: dict[str, Any]) -> bool:
        return True

    def get_path(self, args: dict[str, Any]) -> str:
        return args.get("file_path", "")

    async def description(self, input: dict[str, Any] | None = None) -> str:
        return "Read a file from the local filesystem"

    async def prompt(self) -> str:
        return READ_TOOL_PROMPT

    async def validate_input(
        self, args: dict[str, Any], context: Any = None
    ) -> dict | None:
        file_path = args.get("file_path", "").strip()
        if not file_path:
            return {"result": False, "message": "file_path is required"}

        resolved = os.path.abspath(os.path.expanduser(file_path))
        args["file_path"] = resolved  # Normalize

        if not os.path.exists(resolved):
            return {"result": False, "message": f"File not found: {resolved}"}
        if os.path.isdir(resolved):
            return {"result": False, "message": f"Path is a directory: {resolved}"}

        return None

    async def call(
        self,
        args: dict[str, Any],
        context: Any = None,
        can_use_tool: Any = None,
        on_progress: Any = None,
    ) -> ToolResult:
        file_path = args["file_path"]
        offset = args.get("offset", 1)  # 1-indexed
        limit = args.get("limit")

        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)

            if limit is not None:
                end = offset - 1 + limit
                selected = lines[offset - 1 : end]
            else:
                selected = lines[offset - 1 :]

            content = "".join(selected)
            # Add line numbers (max 10 lines for display)
            MAX_DISPLAY = 10
            numbered = []
            display_count = min(len(selected), MAX_DISPLAY)
            for i, line in enumerate(selected[:display_count], start=offset):
                numbered.append(f"{i:6d}\t{line.rstrip()}")
            if len(selected) > MAX_DISPLAY:
                numbered.append(f"      \t\033[2m… +{len(selected) - MAX_DISPLAY} lines\033[0m")
            display = "\n".join(numbered)

            return ToolResult(data={
                "content": content,
                "display": display,
                "total_lines": total_lines,
                "offset": offset,
                "limit": limit if limit else len(selected),
                "file_path": file_path,
            })
        except PermissionError:
            return ToolResult(data={
                "content": "", "display": f"Permission denied: {file_path}",
                "total_lines": 0, "offset": 0, "limit": 0, "file_path": file_path,
            })

    def map_tool_result_to_block(
        self, output: Any, tool_use_id: str
    ) -> dict[str, Any]:
        display = output.get("display", str(output)) if isinstance(output, dict) else str(output)
        if len(display) > self.max_result_size_chars:
            display = display[:self.max_result_size_chars] + f"\n... (file truncated, {output.get('total_lines', 0)} lines total)"
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": display,
            "is_error": False,
        }
