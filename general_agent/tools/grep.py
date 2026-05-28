"""GrepTool - regex content search using ripgrep.

Reference: cc-haha src/tools/GrepTool/GrepTool.ts
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from general_agent.tools.tool import Tool, ToolResult


class GrepTool(Tool):
    name = "Grep"
    max_result_size_chars = 50_000

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {"type": "string", "description": "Directory to search in (defaults to cwd)"},
                "glob": {"type": "string", "description": "Glob pattern to filter files (e.g. *.py)"},
                "-i": {"type": "boolean", "description": "Case insensitive search"},
                "head_limit": {"type": "integer", "description": "Max output lines (default 100)"},
            },
            "required": ["pattern"],
        }

    def is_read_only(self, args: dict[str, Any]) -> bool:
        return True

    def is_concurrency_safe(self, args: dict[str, Any]) -> bool:
        return True

    async def description(self, input: dict[str, Any] | None = None) -> str:
        return "Search file contents with regex pattern"

    async def prompt(self) -> str:
        return """Search file contents using ripgrep (regex).

- Uses ripgrep (rg) for fast regex search. Falls back to grep if rg not found.
- Use `glob` to filter by file extension (e.g. "*.py", "*.{ts,js}").
- Use `-i` for case-insensitive search."""

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
        glob_filter = args.get("glob", "")
        case_insensitive = args.get("-i", False)
        head_limit = args.get("head_limit", 100)

        cmd = [self._find_ripgrep(), "--no-heading", "--line-number", "--color=never"]
        if case_insensitive:
            cmd.append("-i")
        if glob_filter:
            cmd.extend(["-g", glob_filter])
        cmd.extend(["-e", pattern, search_path])

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30, cwd=os.getcwd(),
            )
            output = result.stdout.strip()
            if not output and result.stderr.strip():
                output = result.stderr.strip()
            out_lines = output.split("\n") if output else [""]
            if len(out_lines) > head_limit:
                output = "\n".join(out_lines[:head_limit])
                output += f"\n... ({len(out_lines) - head_limit} more matches)"
            if not output:
                output = "(no matches)"
            return ToolResult(data={"output": output, "matches": len(out_lines)})
        except (FileNotFoundError, subprocess.SubprocessError):
            return await self._fallback_grep(args)
        except subprocess.TimeoutExpired:
            return ToolResult(data={"output": "(search timed out)", "matches": 0})

    @staticmethod
    def _find_ripgrep() -> str:
        """Find ripgrep binary."""
        for name in ("rg", "rg.exe"):
            for path in os.environ.get("PATH", "").split(os.pathsep):
                candidate = os.path.join(path, name)
                if os.path.isfile(candidate):
                    return candidate
        return "rg"  # Hope it's in PATH

    async def _fallback_grep(self, args: dict[str, Any]) -> ToolResult:
        """Use grep/findstr as fallback when ripgrep not available."""
        pattern = args["pattern"]
        search_path = args.get("path") or os.getcwd()
        glob_filter = args.get("glob", "")
        case_insensitive = args.get("-i", False)
        head_limit = args.get("head_limit", 100)

        # Try grep first, then Windows findstr
        if os.name == "nt":
            return await self._fallback_findstr(pattern, search_path, case_insensitive, head_limit)

        cmd = ["grep", "-rn", "--color=never"]
        if case_insensitive:
            cmd.append("-i")
        if glob_filter:
            cmd.extend(["--include", glob_filter])
        cmd.extend(["-e", pattern, search_path])

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30, cwd=os.getcwd(),
            )
            output = result.stdout.strip()
            lines = output.split("\n") if output else []
            if len(lines) > head_limit:
                output = "\n".join(lines[:head_limit]) + f"\n... ({len(lines) - head_limit} more)"
            if not output:
                output = "(no matches)"
            return ToolResult(data={"output": output, "matches": len(lines)})
        except subprocess.TimeoutExpired:
            return ToolResult(data={"output": "(search timed out)", "matches": 0})

    async def _fallback_findstr(self, pattern: str, search_path: str,
                                 case_insensitive: bool, head_limit: int) -> ToolResult:
        """Windows: use findstr.exe as fallback."""
        cmd = ["findstr", "/s", "/n"]
        if case_insensitive:
            cmd.append("/i")
        cmd.extend([pattern, os.path.join(search_path, "*")])

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30, cwd=os.getcwd(),
            )
            output = result.stdout.strip()
            lines = output.split("\n") if output else []
            if len(lines) > head_limit:
                output = "\n".join(lines[:head_limit])
                output += f"\n... ({len(lines) - head_limit} more matches)"
            if not output:
                output = "(no matches)"
            return ToolResult(data={"output": output, "matches": len(lines)})
        except subprocess.SubprocessError:
            return ToolResult(data={
                "output": "(grep tool not available - install ripgrep or grep)",
                "matches": 0,
            })

    def map_tool_result_to_block(self, output: Any, tool_use_id: str) -> dict:
        text = output.get("output", str(output)) if isinstance(output, dict) else str(output)
        return {"type": "tool_result", "tool_use_id": tool_use_id, "content": text, "is_error": False}
