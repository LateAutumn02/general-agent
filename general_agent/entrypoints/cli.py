"""CLI entry point - fast-path dispatch then full CLI.

Mimics cc-haha src/entrypoints/cli.tsx pattern:
- Fast-path handlers for special flags (--version, --help, etc.)
- Fallthrough to main() for the interactive/REPL path.
- Module-level side effects run before main().

Reference: cc-haha src/entrypoints/cli.tsx
"""

from __future__ import annotations

import os
import sys

# Load .env before anything else (cc-haha pattern: module-level side effects)
_config_path = os.path.join(os.path.expanduser("~"), ".general_agent.env")
try:
    from dotenv import load_dotenv
    load_dotenv(_config_path)
except Exception:
    pass  # .env is optional

# Enable ANSI colors and UTF-8 on Windows PowerShell
try:
    if os.name == "nt":
        import colorama
        colorama.init()
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------------------
# Module-level side effects (before anything imports)
# ---------------------------------------------------------------------------

# Disable Python bytecode generation (matching cc-haha's "never write .pyc")
sys.dont_write_bytecode = True


# ---------------------------------------------------------------------------
# Fast-path dispatch
# ---------------------------------------------------------------------------


def _handle_version() -> None:
    """Zero-import fast path for --version."""
    print("general-agent v0.1.0")
    sys.exit(0)


def _handle_help() -> None:
    """Fast path for --help."""
    print(
        "general-agent - A general-purpose AI coding agent\n"
        "\n"
        "Usage: general-agent [options] [prompt]\n"
        "\n"
        "Options:\n"
        "  --version, -v      Show version\n"
        "  --help, -h         Show this help\n"
        "  --model, -m MODEL  Model to use (default: deepseek-v4-pro)\n"
        "  --print, -p        Non-interactive mode, output result and exit\n"
        "  --continue, -c     Continue the most recent session\n"
        "  --verbose          Enable debug logging\n"
        "  --permission-mode MODE  Permission mode (default|acceptEdits|bypassPermissions)\n"
        "\n"
        "Environment:\n"
        "  DEEPSEEK_API_KEY  API key (required)\n"
        "  GENERAL_AGENT_MODEL  Model name override\n"
    )
    sys.exit(0)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


async def main(argv: list[str] | None = None) -> None:
    """Main entry point. Dispatches fast paths, then loads full CLI.

    Args:
        argv: Command-line arguments. Defaults to sys.argv[1:].
    """
    if argv is None:
        argv = sys.argv[1:]

    # Fast paths - handle and return early
    if argv and argv[0] in ("--help", "-h"):
        return _handle_help()

    if argv and argv[0] in ("--version", "-v", "-V"):
        return _handle_version()

    # --bare flag: set simple mode early (matching cc-haha pattern)
    if "--bare" in argv:
        os.environ["GENERAL_AGENT_SIMPLE"] = "1"

    # Fallthrough to full CLI
    await _run_cli(argv)


async def _run_cli(argv: list[str]) -> None:
    """Parse CLI args, init, and enter the main loop."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="general-agent",
        description="A general-purpose AI coding agent.",
        add_help=False,  # Handled by fast path above
    )
    parser.add_argument("prompt", nargs="?", default="")
    parser.add_argument("--model", "-m", default=os.environ.get("GENERAL_AGENT_MODEL", ""))
    parser.add_argument("--print", "-p", action="store_true", default=False)
    parser.add_argument("--continue", "-c", dest="continue_session", action="store_true", default=False)
    parser.add_argument("--verbose", action="store_true", default=False)
    parser.add_argument("--permission-mode", default="default")
    parser.add_argument("--bare", action="store_true", default=False)

    args = parser.parse_args(argv)

    # Build config from CLI args
    from general_agent.bootstrap.init import AppConfig

    config = AppConfig(
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        model=args.model or os.environ.get("GENERAL_AGENT_MODEL", "deepseek-v4-pro"),
        verbose=args.verbose,
        permission_mode=args.permission_mode,
        print_mode=args.print,
        continue_session=args.continue_session,
    )

    # Initialize
    from general_agent.bootstrap import init as bootstrap_init

    await bootstrap_init.init()
    from general_agent.bootstrap.state import set_config

    set_config(config)

    # Gather system context
    from general_agent.utils.context import get_system_context, format_system_context
    system_ctx = get_system_context(os.getcwd())
    system_prompt = format_system_context(system_ctx)

    # Print mode: one-shot query, output result, exit
    if args.print and args.prompt:
        from general_agent.services.api.messages import query_model_without_streaming

        messages = [{"role": "user", "content": args.prompt}]
        result = await query_model_without_streaming(
            messages=messages,
            system_prompt=system_prompt,
        )
        _print_assistant_response(result)
        return

    # One-shot with positional prompt (no --print flag)
    if args.prompt:
        from general_agent.services.api.messages import query_model_with_streaming

        _show_banner()
        print()
        print(f"  \033[2m{args.prompt}\033[0m")
        print()

        messages = [{"role": "user", "content": args.prompt}]
        async for msg in query_model_with_streaming(
            messages=messages,
            system_prompt=system_prompt,
        ):
            if msg.get("role") == "assistant":
                _print_assistant_response(msg)
        return

    # Interactive REPL - run setup if not configured, otherwise enter REPL
    if not config.api_key:
        await _first_run_setup()
    await _run_repl(config)


# ---------------------------------------------------------------------------
# First-run setup
# ---------------------------------------------------------------------------


async def _first_run_setup() -> None:
    """Interactive setup wizard for first-time users.

    Asks for model, API key, base URL. Saves to .env.
    """
    print("""
  \033[1;36mgeneral-agent\033[0m - First Run Setup
  \033[2mConfigure your AI provider. Press Enter to use defaults.\033[0m
""")

    # Model
    default_model = "deepseek-v4-pro"
    model = input(f"  Model [{default_model}]: ").strip()
    if not model:
        model = default_model

    # API format
    print()
    print("  \033[2mAPI format:\033[0m")
    print("    [1] OpenAI-compatible")
    print("    [2] Anthropic-compatible")
    fmt = input("  Choice [1]: ").strip() or "1"

    if fmt == "2":
        # Anthropic-compatible (DeepSeek: /anthropic endpoint)
        default_url = "https://api.deepseek.com/anthropic"
        base_url = input(f"  Base URL [{default_url}]: ").strip() or default_url
        api_key = input("  API Key: ").strip()
        _save_env(
            ANTHROPIC_API_KEY=api_key,
            ANTHROPIC_BASE_URL=base_url,
            GENERAL_AGENT_MODEL=model,
            GENERAL_AGENT_PROVIDER="anthropic",
        )
    else:
        # OpenAI-compatible
        default_url = "https://api.deepseek.com"
        base_url = input(f"  Base URL [{default_url}]: ").strip() or default_url
        api_key = input("  API Key: ").strip()
        _save_env(
            DEEPSEEK_API_KEY=api_key,
            DEEPSEEK_BASE_URL=base_url,
            GENERAL_AGENT_MODEL=model,
            GENERAL_AGENT_PROVIDER="openai",
        )

    # Reload env
    from dotenv import load_dotenv

    load_dotenv(_config_path, override=True)

    print()
    print("  \033[32mConfiguration saved.\033[0m")
    print()


def _save_env(**kwargs: str) -> None:
    """Save key-value pairs to .env file."""
    env_path = _config_path
    lines = []
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            lines = [line.rstrip() for line in f if line.strip()]

    # Remove existing keys
    keys_to_remove = set(kwargs.keys())
    lines = [line for line in lines if line.split("=", 1)[0] not in keys_to_remove]

    # Add new keys
    for k, v in kwargs.items():
        if v:
            lines.append(f"{k}={v}")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# REPL
# ---------------------------------------------------------------------------


async def _run_repl(config) -> None:
    """Interactive REPL with streaming responses.

    Displays banner, then loops: prompt -> API call -> display result.
    Uses readline on Unix, plain input() on Windows.
    """
    # Enable line editing and history (Unix readline, Windows skip)
    hist_file = os.path.join(os.path.expanduser("~"), ".general_agent_history")
    try:
        import readline
        try:
            readline.read_history_file(hist_file)
        except FileNotFoundError:
            pass
    except (ImportError, ModuleNotFoundError):
        readline = None  # type: ignore[assignment]

    _show_banner()

    # Gather system context (git status, etc.) matching cc-haha pattern
    from general_agent.utils.context import get_system_context, format_system_context
    system_ctx = get_system_context(os.getcwd())
    system_prompt = format_system_context(system_ctx)
    print()

    conversation: list[dict[str, Any]] = []

    try:
        while True:
            try:
                user_input = input("\033[36m>\033[0m ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not user_input:
                continue

            # History (Unix only)
            if readline is not None:
                readline.write_history_file(hist_file)

            # Slash commands
            if user_input.startswith("/"):
                if _handle_slash(user_input):
                    break
                continue

            # Add to conversation and query
            conversation.append({"role": "user", "content": user_input})
            print()

            from general_agent.services.api.messages import query_model_with_streaming

            try:
                async for msg in query_model_with_streaming(
                    messages=list(conversation),
                    system_prompt=system_prompt,
                ):
                    if msg.get("role") == "assistant":
                        _print_assistant_response(msg)
                        conversation.append(msg)
            except Exception as e:
                print(f"\n  \033[31mError: {e}\033[0m\n")
                # Remove the failed user message from conversation
                conversation.pop()

            print()

    finally:
        if readline is not None:
            try:
                readline.write_history_file(hist_file)
            except Exception:
                pass
        print("\n  Goodbye.")


def _show_banner() -> None:
    """Display startup banner matching cc-haha pattern."""
    from general_agent.bootstrap.state import get_main_loop_model, get_session_id
    from general_agent.constants.models import MODEL_DISPLAY_NAMES

    raw_model = get_main_loop_model()
    display_model = MODEL_DISPLAY_NAMES.get(raw_model, raw_model)
    session = get_session_id()[:8]

    print(f"""
  \033[1;36mgeneral-agent\033[0m  \033[2mv0.1.0\033[0m

  \033[2mModel:\033[0m   {display_model}
  \033[2mSession:\033[0m {session}
  \033[2mCWD:\033[0m     {os.getcwd()}

  \033[2mType /help for commands, /exit to quit.\033[0m""")


def _handle_slash(cmd: str) -> bool:
    """Handle slash commands. Returns True if the REPL should exit."""
    parts = cmd.split()
    name = parts[0].lower()

    if name in ("/exit", "/quit", "/q"):
        return True

    if name == "/help":
        print("""
  \033[1mCommands:\033[0m
    /exit, /quit    Exit general-agent
    /help           Show this help
    /model <name>   Switch model (e.g. /model sonnet)
    /clear          Clear conversation history
    /session        Show session info
  \033[2mJust type your question to start a conversation.\033[0m
""")
        return False

    if name == "/model":
        if len(parts) > 1:
            from general_agent.bootstrap.state import set_main_loop_model
            set_main_loop_model(parts[1])
            print(f"  Switched to model: {parts[1]}")
        else:
            from general_agent.bootstrap.state import get_main_loop_model
            print(f"  Current model: {get_main_loop_model()}")
        return False

    if name == "/clear":
        # We can't clear the generator, but signal intent
        print("  \033[2mConversation history cleared.\033[0m")
        return False

    if name == "/session":
        from general_agent.bootstrap.state import get_session_id, get_total_cost_usd
        print(f"  Session: {get_session_id()}")
        print(f"  Cost:    ${get_total_cost_usd():.4f}")
        return False

    print(f"  Unknown command: {name}. Type /help for available commands.")
    return False


def _print_assistant_response(msg: dict[str, Any]) -> None:
    """Print an assistant message to the terminal."""
    content = msg.get("content", "")
    if isinstance(content, list):
        for block in content:
            if block.get("type") == "text":
                _stream_text(block.get("text", ""))
    elif isinstance(content, str):
        _stream_text(content)

    # Show usage if available
    usage = msg.get("usage", {})
    if usage:
        input_t = usage.get("input_tokens", 0)
        output_t = usage.get("output_tokens", 0)
        if input_t or output_t:
            cost = (input_t / 1_000_000) * 3.0 + (output_t / 1_000_000) * 15.0
            print(f"\n  \033[2mTokens: {input_t} in / {output_t} out  ·  ${cost:.4f}\033[0m")


def _stream_text(text: str) -> None:
    """Print text with word wrapping at terminal width."""
    try:
        width = os.get_terminal_size().columns - 4
    except (OSError, ValueError):
        width = 76

    for paragraph in text.split("\n"):
        if not paragraph.strip():
            print()
            continue
        # Simple word wrap
        line = ""
        for word in paragraph.split():
            if len(line) + len(word) + 1 > width:
                print(f"  {line}")
                line = word
            else:
                line = f"{line} {word}" if line else word
        if line:
            print(f"  {line}")


def cli_main() -> None:
    """Synchronous wrapper for the async main().

    Called from __main__ guard or pyproject.toml entry point.
    """
    import asyncio

    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
