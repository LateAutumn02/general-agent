"""BashTool - execute shell commands.

Reference: cc-haha src/tools/BashTool/BashTool.tsx
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from general_agent.tools.tool import PermissionResult, Tool, ToolResult

BASH_TOOL_PROMPT = """Execute a bash command on the user's system.

- Use this to run commands, install packages, build projects, run tests.
- Prefer to run multiple commands in sequence rather than one per call.
- Default working directory: {cwd}.
- The output of the command will be returned to you."""


class BashTool(Tool):
    name = "Bash"
    max_result_size_chars = 30_000

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"},
                "description": {"type": "string", "description": "What this command does"},
                "timeout": {"type": "integer", "description": "Timeout in milliseconds"},
            },
            "required": ["command"],
        }

    def is_read_only(self, args: dict[str, Any]) -> bool:
        cmd = args.get("command", "")
        read_only_prefixes = ("ls", "cat", "head", "tail", "grep", "find",
                              "which", "echo", "pwd", "whoami", "git status",
                              "git log", "git diff", "git branch")
        return any(cmd.startswith(p) for p in read_only_prefixes)

    def is_concurrency_safe(self, args: dict[str, Any]) -> bool:
        return self.is_read_only(args)

    async def description(self, input: dict[str, Any] | None = None) -> str:
        if input and input.get("description"):
            return input["description"]
        return "Execute a shell command"

    async def prompt(self) -> str:
        cwd = os.getcwd()
        return BASH_TOOL_PROMPT.format(cwd=cwd)

    async def validate_input(
        self, args: dict[str, Any], context: Any = None
    ) -> dict | None:
        command = args.get("command", "").strip()
        if not command:
            return {"result": False, "message": "command must not be empty"}

        # Block destructive commands in v1 (simplified sandbox)
        blocked = ("rm -rf /", "mkfs.", "dd if=", ":(){ :|:& };:")
        for pattern in blocked:
            if pattern in command:
                return {"result": False, "message": f"Blocked pattern: {pattern}"}

        return None  # Valid

    async def call(
        self,
        args: dict[str, Any],
        context: Any = None,
        can_use_tool: Any = None,
        on_progress: Any = None,
    ) -> ToolResult:
        """Execute a shell command and return stdout/stderr."""
        command = args["command"]
        timeout = args.get("timeout", 120_000)  # ms

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout / 1000,
                cwd=os.getcwd(),
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            output_parts = []
            if stdout:
                output_parts.append(stdout)
            if stderr:
                output_parts.append(f"[stderr]\n{stderr}")
            output = "\n".join(output_parts) if output_parts else "(no output)"

            return ToolResult(data={
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": result.returncode,
                "output": output,
            })
        except subprocess.TimeoutExpired:
            return ToolResult(data={
                "stdout": "",
                "stderr": f"Command timed out after {timeout}ms",
                "exit_code": -1,
                "output": f"Command timed out after {timeout}ms",
            })
        except Exception as e:
            return ToolResult(data={
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "output": f"Error: {e}",
            })

    def map_tool_result_to_block(
        self, output: Any, tool_use_id: str
    ) -> dict[str, Any]:
        text = output.get("output", str(output)) if isinstance(output, dict) else str(output)
        if len(text) > self.max_result_size_chars:
            text = text[:self.max_result_size_chars] + "\n... (output truncated)"
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": text,
            "is_error": output.get("exit_code", -1) != 0 if isinstance(output, dict) else False,
        }

    async def check_permissions(
        self, args: dict[str, Any], context: Any = None
    ) -> PermissionResult:
        # Read-only commands auto-allow
        if self.is_read_only(args):
            return PermissionResult(behavior="allow", updated_input=args)
        # Write commands: ask for confirmation in default mode
        return PermissionResult(behavior="ask", updated_input=args)
