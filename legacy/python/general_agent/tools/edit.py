"""FileEditTool - modify files using old_string/new_string replacement.

Reference: cc-haha src/tools/FileEditTool/FileEditTool.ts
"""

from __future__ import annotations

import os
from typing import Any

from general_agent.tools.tool import PermissionResult, Tool, ToolResult


class FileEditTool(Tool):
    name = "Edit"
    max_result_size_chars = 100_000

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to edit"},
                "old_string": {"type": "string", "description": "The text to replace"},
                "new_string": {"type": "string", "description": "The text to replace with"},
                "replace_all": {"type": "boolean", "description": "Replace all occurrences (default false)"},
            },
            "required": ["file_path", "old_string", "new_string"],
        }

    def is_read_only(self, args: dict[str, Any]) -> bool:
        return False

    def get_path(self, args: dict[str, Any]) -> str:
        return args.get("file_path", "")

    async def description(self, input: dict[str, Any] | None = None) -> str:
        return "Edit a file by replacing old_string with new_string"

    async def prompt(self) -> str:
        return """Edit a file by replacing old_string with new_string.

- Use this for small targeted changes. For full file rewrites, use Write.
- old_string must match exactly, including whitespace and indentation.
- Set replace_all=True to replace all occurrences."""

    async def validate_input(
        self, args: dict[str, Any], context: Any = None
    ) -> dict | None:
        file_path = args.get("file_path", "").strip()
        old_string = args.get("old_string", "")
        new_string = args.get("new_string", "")

        if not file_path:
            return {"result": False, "message": "file_path is required"}

        resolved = os.path.abspath(os.path.expanduser(file_path))
        args["file_path"] = resolved

        if old_string == new_string:
            return {"result": False, "message": "old_string and new_string are identical"}

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
        old_string = args["old_string"]
        new_string = args["new_string"]
        replace_all = args.get("replace_all", False)

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            count = content.count(old_string)
            if count == 0:
                return ToolResult(data={
                    "type": "error", "file_path": file_path,
                    "message": f"old_string not found in {file_path}",
                })

            if replace_all:
                updated = content.replace(old_string, new_string)
                replacements = count
            else:
                if count > 1:
                    return ToolResult(data={
                        "type": "error", "file_path": file_path,
                        "message": f"old_string appears {count} times. Use replace_all=True or make it more specific.",
                    })
                updated = content.replace(old_string, new_string, 1)
                replacements = 1

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(updated)

            # Build diff display
            display = _build_diff_display(file_path, old_string, new_string, replacements)
            short = os.path.basename(file_path)

            return ToolResult(data={
                "type": "edit",
                "file_path": file_path,
                "replacements": replacements,
                "lines_changed": old_string.count("\n") + 1,
                "display": display or f"  Edit {short}: \033[32m+{len(new_string)}\033[0m \033[31m-{len(old_string)}\033[0m",
            })
        except PermissionError:
            return ToolResult(data={
                "type": "error", "file_path": file_path,
                "message": f"Permission denied: {file_path}",
            })

    def map_tool_result_to_block(
        self, output: Any, tool_use_id: str
    ) -> dict[str, Any]:
        if isinstance(output, dict) and output.get("type") == "error":
            return {"type": "tool_result", "tool_use_id": tool_use_id,
                    "content": output["message"], "is_error": True}
        return {"type": "tool_result", "tool_use_id": tool_use_id,
                "content": f"Edited {output.get('file_path', '')}: {output.get('replacements', 0)} replacement(s)",
                "is_error": False}

    async def check_permissions(
        self, args: dict[str, Any], context: Any = None
    ) -> PermissionResult:
        return PermissionResult(behavior="ask", updated_input=args)


# ---------------------------------------------------------------------------
# Diff display (VS Code style)
# ---------------------------------------------------------------------------

R = "\033[0m"
D = "\033[2m"
RD = "\033[31m"
GN = "\033[32m"
BG_RD = "\033[41m"
BG_GN = "\033[42m"


def _build_diff_display(file_path: str, old: str, new: str, count: int) -> str:
    """Build a VS Code-style diff rendering with colored backgrounds."""
    short = os.path.basename(file_path)
    lines: list[str] = []

    # Header
    lines.append(f"  {D}Edit{R} {short}: {count} replacement(s)")

    # Old → New with inline diff markers
    old_lines = old.split("\n")
    new_lines = new.split("\n")

    # Show the diff: removed lines in red bg, added in green bg
    for line in old_lines:
        if line.strip():
            lines.append(f"  {BG_RD}{D}- {line}{R}")
    for line in new_lines:
        if line.strip():
            lines.append(f"  {BG_GN}{D}+ {line}{R}")

    return "\n".join(lines)
