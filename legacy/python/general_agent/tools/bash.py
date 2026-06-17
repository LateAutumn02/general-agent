"""BashTool - execute shell commands with formatted UI output.

Reference: cc-haha src/tools/BashTool/BashTool.tsx, UI.tsx, BashToolResultMessage.tsx
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any

from general_agent.tools.tool import PermissionResult, Tool, ToolResult
from general_agent.tools.bash_ui import (
    BashOut,
    format_command_display,
    format_duration,
    is_silent_command,
    summarize_result,
)

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
        """Execute a shell command and return structured BashOut."""
        command = args["command"]
        timeout = args.get("timeout", 120_000)
        silent = is_silent_command(command)

        # Sandbox wrapping
        bypass = args.get("dangerouslyDisableSandbox", False)
        from general_agent.sandbox.settings import should_use_sandbox, is_sandbox_enabled, get_settings
        sandboxed = is_sandbox_enabled() and should_use_sandbox(command) and not (bypass and get_settings().allow_unsandboxed)
        if sandboxed:
            if not _wrap_sandbox(command):
                out = BashOut(
                    stderr="Sandbox: command blocked (access outside project directory)",
                    exit_code=1,
                    is_silent=silent,
                )
                return self._build_result(out)

        # Execute
        t0 = time.monotonic()
        try:
            # Use system encoding on Windows (GBK etc.), UTF-8 elsewhere
            _enc = "utf-8"
            if os.name == "nt":
                import locale
                try:
                    _enc = locale.getpreferredencoding() or "gbk"
                except Exception:
                    _enc = "gbk"
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding=_enc,
                errors="replace",
                timeout=timeout / 1000,
                cwd=os.getcwd(),
            )
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            out = BashOut(
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                exit_code=result.returncode,
                duration_ms=elapsed_ms,
                is_silent=silent,
            )
            return self._build_result(out)

        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            out = BashOut(
                stderr=f"Command timed out after {format_duration(timeout)}",
                exit_code=-1,
                timed_out=True,
                duration_ms=elapsed_ms,
                is_silent=silent,
            )
            return self._build_result(out)

        except Exception as e:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            out = BashOut(
                stderr=str(e),
                exit_code=-1,
                duration_ms=elapsed_ms,
                is_silent=silent,
            )
            return self._build_result(out)

    # ------------------------------------------------------------------
    # Output formatting
    # ------------------------------------------------------------------

    def _build_result(self, out: BashOut) -> ToolResult:
        """Build a ToolResult from BashOut with formatted display strings."""
        # Model-side: clean text (ANSI stripped for API)
        model_text = self._format_for_model(out)

        # User-side display text (ANSI preserved, truncated)
        display_text = self._format_for_display(out)

        return ToolResult(data={
            "stdout": out.stdout,
            "stderr": out.stderr,
            "exit_code": out.exit_code,
            "interrupted": out.interrupted,
            "timed_out": out.timed_out,
            "duration_ms": out.duration_ms,
            "is_silent": out.is_silent,
            "output": model_text,         # for model: clean text
            "display": display_text,       # for user: colored + truncated
            "summary": summarize_result(out),  # one-line status
        })

    def _format_for_model(self, out: BashOut) -> str:
        """Build the text sent to the model (API tool_result).

        - stdout first, stderr prefixed with [stderr]
        - ANSI codes stripped (waste tokens)
        - No output: contextual message based on command type
        """
        from general_agent.tools.bash_ui import strip_ansi

        parts: list[str] = []
        if out.stdout:
            parts.append(strip_ansi(out.stdout))
        if out.stderr:
            parts.append(f"[stderr]\n{strip_ansi(out.stderr)}")

        if not parts:
            if out.interrupted:
                return "Command interrupted by user"
            if out.timed_out:
                return f"Command timed out ({format_duration(out.duration_ms)})"
            if out.is_silent:
                return "Done (command completed successfully with no output)"
            return "(no output)"

        return "\n".join(parts)

    def _format_for_display(self, out: BashOut):
        """Build a Rich Panel for the bash output display."""
        from general_agent.tools.bash_ui import render_bash_panel
        return render_bash_panel(out)

    def map_tool_result_to_block(
        self, output: Any, tool_use_id: str
    ) -> dict[str, Any]:
        """Format tool output as an API-compatible tool_result block.

        Uses the 'output' field (model-side text) for the API.
        """
        if isinstance(output, dict):
            text = output.get("output", str(output))
            is_error = output.get("exit_code", -1) != 0
        else:
            text = str(output)
            is_error = False

        if len(text) > self.max_result_size_chars:
            text = text[:self.max_result_size_chars] + "\n... (output truncated)"

        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": text,
            "is_error": is_error,
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
        paths = re.findall(r'["\']?([A-Za-z]:(?:\\[^"\'\s]*)+)', command)
        for p in paths:
            p_clean = p.replace("\\", "/").lower()
            if not p_clean.startswith(cwd):
                return ""  # Blocked

    return command
