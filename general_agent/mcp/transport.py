"""JSON-RPC stdio transport — ~~asyncio subprocess + newline-delimited JSON~~.

Manages one MCP server process:
  - Spawn via asyncio.create_subprocess_exec
  - Send/receive JSON-RPC messages over stdin/stdout (one JSON object per line)
  - Background reader task dispatches responses to waiting Futures

Reference: cc-haha src/services/mcp/client.ts (StdioClientTransport usage)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from general_agent.mcp.types import MCPServerConfig

logger = logging.getLogger("general_agent.mcp.transport")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MCPTransportError(Exception):
    """Base for MCP transport errors."""


class ServerDisconnectedError(MCPTransportError):
    """Server process terminated or pipe broken."""


# ---------------------------------------------------------------------------
# MCPServerProcess
# ---------------------------------------------------------------------------


class MCPServerProcess:
    """Manages a single stdio MCP server process.

    Spawns the child process and communicates via JSON-RPC 2.0
    (newline-delimited JSON on stdin/stdout).

    Usage::

        proc = MCPServerProcess("myserver", config)
        await proc.start()
        result = await proc.send_request("tools/list")
        await proc.close()
    """

    def __init__(self, name: str, config: MCPServerConfig) -> None:
        self.name = name
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._msg_id = 0
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._closed = False

    # --- public ---

    @property
    def is_connected(self) -> bool:
        return (
            self._process is not None
            and self._process.returncode is None
            and not self._closed
        )

    async def start(self) -> None:
        """Spawn the child process and begin reading stdout."""
        if self._process is not None:
            return

        logger.debug("MCP spawning %s: %s %s",
                     self.name, self.config.command, self.config.args)

        # Build environment: inherit parent env + server overrides
        env = os.environ.copy()
        if self.config.env:
            env.update(self.config.env)

        self._process = await asyncio.create_subprocess_exec(
            self.config.command,
            *self.config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        self._reader_task = asyncio.create_task(
            self._reader_loop(), name=f"mcp-reader-{self.name}"
        )

    async def send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a JSON-RPC request and await the matching response.

        Args:
            method: JSON-RPC method name (e.g. "tools/list", "tools/call")
            params: Method parameters dict (optional)

        Returns:
            The "result" field from the JSON-RPC response.

        Raises:
            ServerDisconnectedError: if the process is not connected.
            MCPTransportError: if the response contains a JSON-RPC error.
        """
        if not self.is_connected:
            raise ServerDisconnectedError(
                f"MCP server '{self.name}' is not connected"
            )

        self._msg_id += 1
        msg_id = self._msg_id

        request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        future: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = future

        try:
            line = json.dumps(request, ensure_ascii=False) + "\n"
            assert self._process is not None and self._process.stdin is not None
            self._process.stdin.write(line.encode("utf-8"))
            await self._process.stdin.drain()

            response = await future

            if "error" in response:
                err = response["error"]
                raise MCPTransportError(
                    f"MCP error [{err.get('code', -1)}]: {err.get('message', 'unknown')}"
                )
            return response.get("result", {})
        finally:
            self._pending.pop(msg_id, None)

    async def send_notification(self, method: str) -> None:
        """Send a JSON-RPC notification (no id, no response expected).

        Used for the ``notifications/initialized`` handshake step.
        """
        if not self.is_connected:
            return

        notification = {
            "jsonrpc": "2.0",
            "method": method,
        }
        line = json.dumps(notification, ensure_ascii=False) + "\n"
        assert self._process is not None and self._process.stdin is not None
        self._process.stdin.write(line.encode("utf-8"))
        await self._process.stdin.drain()

    async def close(self) -> None:
        """Terminate the server process and release resources.

        Sends SIGTERM, waits 5s, then SIGKILL. Cancels all pending Futures.
        """
        self._closed = True

        # Fail all pending futures
        for future in self._pending.values():
            if not future.done():
                future.set_exception(
                    ServerDisconnectedError(f"Server '{self.name}' closed")
                )
        self._pending.clear()

        # Cancel reader
        if self._reader_task is not None and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        self._reader_task = None

        # Terminate process
        if self._process is not None and self._process.returncode is None:
            try:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self._process.kill()
                    await self._process.wait()
            except ProcessLookupError:
                pass

        self._process = None

    # --- internals ---

    async def _reader_loop(self) -> None:
        """Background coroutine: read stdout lines, dispatch to waiting Futures."""
        assert self._process is not None and self._process.stdout is not None

        try:
            while self.is_connected:
                line = await self._process.stdout.readline()
                if not line:
                    break  # EOF → server exited

                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                try:
                    msg: dict[str, Any] = json.loads(line_str)
                except json.JSONDecodeError:
                    logger.warning("MCP %s: invalid JSON line: %s",
                                   self.name, line_str[:200])
                    continue

                msg_id = msg.get("id")
                if msg_id is not None and msg_id in self._pending:
                    self._pending[msg_id].set_result(msg)
                # Notifications (no id) are silently dropped
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("MCP %s reader loop crashed", self.name)
        finally:
            # Signal disconnect to all pending futures
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(
                        ServerDisconnectedError(f"Server '{self.name}' disconnected")
                    )
            self._pending.clear()
