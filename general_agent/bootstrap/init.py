"""One-time initialization (config, env, graceful shutdown).

memoize-wrapped so init() runs exactly once per process.
Callers await the cached future on subsequent calls.

Reference: cc-haha src/entrypoints/init.ts
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
import signal

logger = logging.getLogger("general_agent")


# ---------------------------------------------------------------------------
# AppConfig
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class AppConfig:
    """Parsed CLI / env configuration for a session."""

    api_key: str = ""
    model: str = ""
    verbose: bool = False
    permission_mode: str = "default"  # default | acceptEdits | bypassPermissions
    max_turns: int = 100
    print_mode: bool = False  # -p/--print flag
    continue_session: bool = False  # --continue flag
    custom_system_prompt: str = ""

    @classmethod
    def from_env(cls) -> AppConfig:
        """Build config from environment variables and defaults."""
        api_key = os.environ.get("API_KEY", "")
        from general_agent.constants.models import DEFAULT_MODEL
        return cls(
            api_key=api_key,
            model=os.environ.get("MODEL", DEFAULT_MODEL),
            verbose=bool(os.environ.get("VERBOSE", "")),
            permission_mode=os.environ.get("PERMISSION_MODE", "default"),
            print_mode=not os.isatty(0),
        )


# ---------------------------------------------------------------------------
# Cleanup registry
# ---------------------------------------------------------------------------

_cleanup_handlers: list[asyncio.coroutine] = []


def register_cleanup(handler) -> None:
    """Register an async cleanup function to run on graceful shutdown."""
    _cleanup_handlers.append(handler)


async def _run_cleanup() -> None:
    logger.debug("Running %d cleanup handlers", len(_cleanup_handlers))
    for handler in _cleanup_handlers:
        try:
            await handler
        except Exception:
            logger.exception("Cleanup handler failed")


def _signal_handler(signum, frame) -> None:
    """Handle SIGINT/SIGTERM - schedule graceful shutdown."""
    logger.info("Received signal %s, shutting down", signum)
    # Reset cursor (cc-haha pattern)
    print("\033[?25h", end="", flush=True)
    raise SystemExit(0)


# ---------------------------------------------------------------------------
# init() - memoized
# ---------------------------------------------------------------------------

_init_promise: asyncio.Future | None = None


async def init() -> None:
    """One-time initialization. Runs exactly once per process.

    Subsequent calls return immediately (already initialized).
    """
    global _init_promise

    if _init_promise is not None:
        await _init_promise
        return

    _init_promise = asyncio.get_event_loop().create_future()

    try:
        await _do_init()
        _init_promise.set_result(None)
    except Exception as e:
        _init_promise.set_exception(e)
        raise


async def _do_init() -> None:
    """Actual initialization logic."""

    # 1. Validate environment
    _check_node_version()  # Python equivalent: Python 3.12+

    # 2. Load config
    config = AppConfig.from_env()
    _validate_config(config)

    # 3. Apply environment
    if config.verbose:
        logging.basicConfig(level=logging.DEBUG)

    # 4. Register signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # 5. Fire-and-forget background tasks
    # (Phase 1: stub - will add OAuth, IDE detection, repo detection later)
    # TODO: preconnectAnthropicApi() - TCP+TLS preconnect

    # 6. Register MCP cleanup handler
    try:
        from general_agent.mcp import shutdown_mcp
        register_cleanup(shutdown_mcp)
    except ImportError:
        pass  # MCP module not available (harmless)

    # 7. Import STATE and apply config
    from general_agent.bootstrap.state import set_config

    set_config(config)

    logger.info("general-agent initialized. session=%s model=%s",
                _get_session_id(), config.model or "default")


def _check_node_version() -> None:
    """Ensure Python >= 3.12."""
    import sys
    if sys.version_info < (3, 12):
        logger.warning(
            "general-agent requires Python 3.12+. Current: %s",
            sys.version,
        )


def _validate_config(config: AppConfig) -> None:
    """Validate required config fields. Exit with error if missing."""
    if not config.api_key:
        # Interactive: proceed (setup wizard will run). Non-interactive: exit.
        if not os.isatty(0):
            raise SystemExit("No API key configured. Run `glagent` interactively to set up.")


def _get_session_id() -> str:
    """Avoid circular import: lazy import of state."""
    from general_agent.bootstrap.state import get_session_id
    return get_session_id()
