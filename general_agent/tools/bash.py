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
                "dangerouslyDisableSandbox": {"type": "boolean", "description": "Bypass sandbox for this command (requires user approval)"},
            },
            "required": ["command"],
        }

    def is_read_only(self, args: dict[str, Any]) -> bool:
        """Everything is read-only unless it matches destructive patterns."""
        cmd = args.get("command", "")
        destructive_patterns = (
            "> ", ">> ", "| tee ", "rm ", "mv ", "cp ", "chmod ",
            "chown ", "pip install", "npm install", "apt install",
            "brew install", "make ", "dd ", "mkfs", ":(){",
        )
        return not any(p in cmd for p in destructive_patterns)

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
        """Execute a shell command, optionally sandboxed."""
        command = args["command"]
        timeout = args.get("timeout", 120_000)

        # Sandbox wrapping (skipped if dangerouslyDisableSandbox is set)
        bypass = args.get("dangerouslyDisableSandbox", False)
        from general_agent.sandbox.settings import should_use_sandbox, is_sandbox_enabled, get_settings
        sandboxed = is_sandbox_enabled() and should_use_sandbox(command) and not (bypass and get_settings().allow_unsandboxed)
        if sandboxed:
            if not _wrap_sandbox(command):
                return ToolResult(data={"stdout": "", "stderr": "Sandbox: command blocked", "exit_code": 1, "output": "Sandbox: command blocked (access outside project directory)"})

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
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
        # dangerouslyDisableSandbox: requires explicit approval
        if args.get("dangerouslyDisableSandbox"):
            from general_agent.sandbox.settings import get_settings
            settings = get_settings()
            if not settings.allow_unsandboxed:
                return PermissionResult(behavior="deny",
                    message="Unsandboxed commands are disabled by sandbox settings")
            return PermissionResult(behavior="ask",
                message="This command bypasses sandbox. Confirm to proceed.",
                updated_input=args)
        # Read-only commands auto-allow
        if self.is_read_only(args):
            return PermissionResult(behavior="allow", updated_input=args)
        return PermissionResult(behavior="ask", updated_input=args)


def _wrap_sandbox(command: str) -> str:
    """Wrap a command for sandboxed execution. Returns '' if blocked."""
    import os
    import shutil

    if os.name == "posix":
        if shutil.which("seatbelt"):
            return f"seatbelt -- {command}"
        if shutil.which("bwrap"):
            return f"bwrap --ro-bind / / --ro-bind /tmp /tmp --dev /dev --proc /proc -- /bin/sh -c '{command}'"

    # Windows pseudo-sandbox: block commands accessing paths outside project dir
    if os.name == "nt":
        import re
        cwd = os.getcwd().replace("\\", "/").lower()
        # Check for absolute paths outside project
        paths = re.findall(r'["\']?([A-Za-z]:(?:\\[^"\'\s]*)+)', command)
        for p in paths:
            p_clean = p.replace("\\", "/").lower()
            if not p_clean.startswith(cwd):
                return ""  # Blocked

    return command
