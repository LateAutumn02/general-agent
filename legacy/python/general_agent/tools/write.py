"""FileWriteTool - create or overwrite files.

Reference: cc-haha src/tools/FileWriteTool/FileWriteTool.ts
"""

from __future__ import annotations

import os
from typing import Any

from general_agent.tools.tool import PermissionResult, Tool, ToolResult


class FileWriteTool(Tool):
    name = "Write"
    max_result_size_chars = 100_000

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["file_path", "content"],
        }

    def is_read_only(self, args: dict[str, Any]) -> bool:
        return False

    def get_path(self, args: dict[str, Any]) -> str:
        return args.get("file_path", "")

    async def description(self, input: dict[str, Any] | None = None) -> str:
        return "Write a file to the local filesystem"

    async def prompt(self) -> str:
        return """Write a file to the local filesystem.

- Creates the file if it does not exist, overwrites if it does.
- Parent directories will be created automatically."""

    async def validate_input(
        self, args: dict[str, Any], context: Any = None
    ) -> dict | None:
        file_path = args.get("file_path", "").strip()
        if not file_path:
            return {"result": False, "message": "file_path is required"}

        resolved = os.path.abspath(os.path.expanduser(file_path))
        args["file_path"] = resolved

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
        content = args["content"]

        existed = os.path.exists(file_path)
        try:
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except PermissionError:
            return ToolResult(data={
                "type": "error", "file_path": file_path,
                "message": f"Permission denied: {file_path}",
            })

        return ToolResult(data={
            "type": "create" if not existed else "update",
            "file_path": file_path,
            "content": content,
            "lines": content.count("\n") + 1,
        })

    def map_tool_result_to_block(
        self, output: Any, tool_use_id: str
    ) -> dict[str, Any]:
        if isinstance(output, dict) and output.get("type") == "error":
            return {"type": "tool_result", "tool_use_id": tool_use_id,
                    "content": output["message"], "is_error": True}
        return {"type": "tool_result", "tool_use_id": tool_use_id,
                "content": f"Wrote {output.get('lines', 0)} lines to {output.get('file_path', '')}",
                "is_error": False}

    async def check_permissions(
        self, args: dict[str, Any], context: Any = None
    ) -> PermissionResult:
        return PermissionResult(behavior="ask", updated_input=args)
