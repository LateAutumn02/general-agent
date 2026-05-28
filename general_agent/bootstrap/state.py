"""Global session state singleton.

Module-level STATE object, created at import time.
All access through getter/setter functions (no direct field access).

Reference: cc-haha src/bootstrap/state.ts
"""

from __future__ import annotations

import os
import time
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from general_agent.bootstrap.init import AppConfig


# ---------------------------------------------------------------------------
# Internal state representation
# ---------------------------------------------------------------------------

# In-memory representation of global state.
# Python: plain dict for simplicity. Access exclusively through getter/setter functions.
_state: dict[str, Any] = {}


def _get_initial_state() -> dict[str, Any]:
    """Factory for a fresh state dict with all default values.

    Used by module load AND reset_state_for_tests().
    """
    cwd = os.path.realpath(os.getcwd())
    return {
        # Session identity
        "session_id": str(uuid.uuid4()),
        "start_time": time.time(),
        "last_interaction_time": time.time(),
        # Directories
        "original_cwd": cwd,
        "project_root": cwd,
        "cwd": cwd,
        # Cost / usage
        "total_cost_usd": 0.0,
        "total_api_duration_ms": 0,
        # Flags
        "is_interactive": os.isatty(0),
        "verbose": False,
        # Model
        "main_loop_model": "",
        # Settings
        "settings": {},
        # Tools
        "tools": [],
        "commands": [],
        # Tasks / todos
        "todos": {},
        # Memoized contexts
        "system_prompt_section_cache": {},
        "invoked_skills": {},
    }


# Initialize at module load time
_state = _get_initial_state()


# ---------------------------------------------------------------------------
# Getters
# ---------------------------------------------------------------------------

def get_session_id() -> str:
    return _state["session_id"]


def get_project_root() -> str:
    return _state["project_root"]


def get_cwd() -> str:
    return _state["cwd"]


def get_original_cwd() -> str:
    return _state["original_cwd"]


def is_interactive() -> bool:
    return _state["is_interactive"]


def is_verbose() -> bool:
    return _state["verbose"]


def get_total_cost_usd() -> float:
    return _state["total_cost_usd"]


def get_total_api_duration_ms() -> int:
    return _state["total_api_duration_ms"]


def get_main_loop_model() -> str:
    from general_agent.constants.models import DEFAULT_MODEL
    return _state["main_loop_model"] or os.environ.get("GENERAL_AGENT_MODEL", DEFAULT_MODEL)


def get_settings() -> dict[str, Any]:
    return _state["settings"]


def get_tools() -> list:
    return _state["tools"]


def get_commands() -> list:
    return _state["commands"]


def get_todos() -> dict[str, Any]:
    return _state["todos"]


# ---------------------------------------------------------------------------
# Setters
# ---------------------------------------------------------------------------

def set_cwd(path: str) -> None:
    _state["cwd"] = path


def set_project_root(path: str) -> None:
    _state["project_root"] = path


def set_original_cwd(path: str) -> None:
    _state["original_cwd"] = path


def set_interactive(val: bool) -> None:
    _state["is_interactive"] = val


def set_verbose(val: bool) -> None:
    _state["verbose"] = val


def set_main_loop_model(model: str) -> None:
    _state["main_loop_model"] = model


def set_settings(settings: dict[str, Any]) -> None:
    _state["settings"] = settings


def set_tools(tools: list) -> None:
    _state["tools"] = tools


def set_commands(commands: list) -> None:
    _state["commands"] = commands


def set_config(config: AppConfig) -> None:
    """Bulk update from AppConfig."""
    if config.model:
        _state["main_loop_model"] = config.model
    if config.verbose:
        _state["verbose"] = config.verbose


def add_to_total_cost_usd(cost: float) -> None:
    _state["total_cost_usd"] += cost


def add_to_total_api_duration(ms: int) -> None:
    _state["total_api_duration_ms"] += ms


def touch_last_interaction() -> None:
    _state["last_interaction_time"] = time.time()


def regenerate_session_id() -> str:
    """For session switching (e.g. /resume)."""
    new_id = str(uuid.uuid4())
    _state["session_id"] = new_id
    return new_id


# ---------------------------------------------------------------------------
# Test utilities
# ---------------------------------------------------------------------------

def reset_state_for_tests() -> None:
    """Wipe and re-initialize state. Only for test isolation."""
    global _state
    _state = _get_initial_state()
