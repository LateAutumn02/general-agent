"""MCP configuration loading — ~~.mcp.json + user settings~~.

Loads MCP server definitions from:
  1.  Project-level .mcp.json (walks up from cwd, closer files win)
  2.  User-level ~/.glagent/mcp_settings.json
Project config overrides user config for same-named servers.

Reference: cc-haha src/services/mcp/config.ts, docs/mcp/flow.md
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from general_agent.mcp.types import MCPServerConfig

logger = logging.getLogger("general_agent.mcp.config")

# User-level MCP settings file
_USER_MCP_FILE = os.path.join(os.path.expanduser("~"), ".glagent", "mcp_settings.json")


def load_user_mcp_config() -> dict[str, MCPServerConfig]:
    """Load MCP servers from user home directory config."""
    if not os.path.isfile(_USER_MCP_FILE):
        return {}

    try:
        with open(_USER_MCP_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return _parse_servers(data.get("mcpServers", {}))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load user MCP config: %s", e)
        return {}


def load_project_mcp_config(cwd: str) -> dict[str, MCPServerConfig]:
    """Walk from filesystem root to cwd, merging .mcp.json files.

    Closer-to-cwd files override ancestor files (like cc-haha's hierarchical merge).
    """
    servers: dict[str, MCPServerConfig] = {}

    try:
        resolved = Path(cwd).resolve()
    except OSError:
        resolved = Path(cwd)

    parts = resolved.parts
    # Walk from root to cwd (index 1 because part 0 is drive root, e.g. "/" or "C:")
    for i in range(1, len(parts) + 1):
        partial = os.path.join(*parts[:i]) if i > 1 else str(parts[0])
        # On Windows, drive root needs a trailing separator to be a valid path
        if os.name == "nt" and i == 1 and not partial.endswith(os.sep):
            partial += os.sep
        mcp_json = os.path.join(partial, ".mcp.json")
        if os.path.isfile(mcp_json):
            _merge_file(servers, mcp_json)

    return servers


def get_mcp_servers(cwd: str) -> dict[str, MCPServerConfig]:
    """Merge user + project MCP servers. Project overrides user for same keys."""
    servers = load_user_mcp_config()
    project = load_project_mcp_config(cwd)
    servers.update(project)  # project wins
    return servers


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _merge_file(servers: dict[str, MCPServerConfig], path: str) -> None:
    """Read and merge .mcp.json from a single file path."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    parsed = _parse_servers(data.get("mcpServers", {}))
    servers.update(parsed)


def _parse_servers(raw: dict[str, Any]) -> dict[str, MCPServerConfig]:
    """Convert raw JSON dict to MCPServerConfig objects."""
    result: dict[str, MCPServerConfig] = {}
    for name, cfg in raw.items():
        if not isinstance(cfg, dict):
            continue
        if not cfg.get("command"):
            continue  # stdio servers require a command

        result[name] = MCPServerConfig(
            command=cfg.get("command", ""),
            args=cfg.get("args", []),
            env=cfg.get("env", {}),
        )
    return result
