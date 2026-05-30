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

    # Print mode: one-shot query with tools
    if args.print and args.prompt:
        from general_agent.agent.loop import AgentState, run_agent
        from general_agent.tools.factory import create_registry
        from general_agent.mcp import init_mcp_servers
        registry = create_registry()
        await init_mcp_servers(registry, os.getcwd())
        state = AgentState(
            messages=[{"role": "user", "content": args.prompt}],
            tool_registry=registry,
            git_context=system_prompt,
            max_turns=5,
        )
        result_text, _ = await run_agent(state)
        if result_text:
            _stream_text(result_text)
        print()
        return

    # One-shot with positional prompt
    if args.prompt:
        from general_agent.agent.loop import AgentState, run_agent
        from general_agent.tools.factory import create_registry
        from general_agent.mcp import init_mcp_servers
        _show_banner()
        print()
        print(f"  \033[2m{args.prompt}\033[0m")
        print()
        registry = create_registry()
        await init_mcp_servers(registry, os.getcwd())
        state = AgentState(
            messages=[{"role": "user", "content": args.prompt}],
            tool_registry=registry,
            git_context=system_prompt,
            max_turns=5,
        )
        result_text, all_msgs = await run_agent(state)
        for msg in reversed(all_msgs):
            if msg.get("role") == "assistant":
                _print_assistant_response(msg)
                break
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

    # Gather system context and register tools
    from general_agent.utils.context import get_system_context, format_system_context
    system_ctx = get_system_context(os.getcwd())
    git_context = format_system_context(system_ctx)

    from general_agent.tools.factory import create_registry
    registry = create_registry()

    # ── MCP init ──
    from general_agent.mcp import init_mcp_servers, get_server_count, get_tool_count
    mcp_servers = await init_mcp_servers(registry, os.getcwd())
    if mcp_servers:
        print(f"  MCP: {mcp_servers} server(s), {get_tool_count()} tool(s)")

    from general_agent.agent.loop import AgentState, run_agent
    from general_agent.memory.store import MemoryStore

    # Load memories + check AutoDream
    memory_store = MemoryStore()
    memory_text = memory_store.format_for_prompt()

    # AutoDream: consolidate stale memories at startup
    if memory_store.should_dream():
        print("  \033[2mMemory consolidation needed...\033[0m")
        dream_prompt = memory_store.build_dream_prompt()
        # Will be injected as first "user message" so agent handles it
        # In REPL, this shows at first prompt. In one-shot, it runs automatically.
        # For now, just touch lock and skip (no fork agent to run it automatically)
        memory_store.touch_dream_lock()

    # Load skills
    from general_agent.skills.loader import scan_skills, format_skills_for_prompt, get_slash_commands
    skills = scan_skills(os.getcwd())
    skills_text = format_skills_for_prompt(skills)
    skill_cmds = get_slash_commands(skills)
    if skills:
        print(f"  Loaded {len(skills)} skill(s): {', '.join(s.name for s in skills)}")

    prompt_extra = memory_text
    if skills_text:
        prompt_extra += "\n" + skills_text

    # Shared AgentState across turns (cc-haha: preserves conversation)
    state = AgentState(
        tool_registry=registry,
        git_context=git_context,
        system_prompt_extra=prompt_extra,
        memory_store=memory_store,
        auto_memory=memory_store.is_enabled(),
        max_turns=10,
    )
    print()

    try:
        while True:
            try:
                user_input = input("\033[36m>\033[0m ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not user_input:
                continue

            if readline is not None:
                readline.write_history_file(hist_file)

            if user_input.startswith("/"):
                # Built-in commands take priority over skills
                result = await _handle_slash(user_input, state)
                if result:
                    break
                if result is not None:  # Handled (returned False = continue REPL)
                    continue
                # Fallback: check if this is a skill invocation
                skill_name = user_input[1:].split()[0].lower()
                if skill_name in skill_cmds:
                    skill = skill_cmds[skill_name]
                    state.messages.append({"role": "user", "content": skill.prompt})
                    state.messages.append({"role": "user", "content": f"Execute the skill: {skill.name}"})
                    print(f"  \033[2mSkill '{skill.name}' activated.\033[0m")
                    result_text, all_messages = await run_agent(
                        state, on_progress=lambda msg: print(msg, flush=True))
                    for msg in reversed(all_messages):
                        if msg.get("role") == "assistant":
                            _print_assistant_response(msg)
                            break
                    continue
                continue

            print()

            # Append user message to shared state
            state.messages.append({"role": "user", "content": user_input})

            try:
                result_text, all_messages = await run_agent(
                    state,
                    on_progress=lambda msg: print(msg, flush=True),
                    on_permission=_ask_permission)

                # Show final response with usage
                if result_text and ("stopped" in result_text.lower() or "repetition" in result_text.lower()):
                    print(f"  \033[31m⚠ {result_text}\033[0m")
                    print("  \033[2mTip: use /compact to compress conversation, /clear to reset.\033[0m")
                else:
                    for msg in reversed(all_messages):
                        if msg.get("role") == "assistant":
                            _print_assistant_response(msg)
                            break

            except Exception as e:
                print(f"\n  \033[31mError: {e}\033[0m\n")

            print()

    finally:
        if readline is not None:
            try:
                readline.write_history_file(hist_file)
            except Exception:
                pass
        print("\n  Goodbye.")


def _ask_permission(name: str, args: dict[str, Any]) -> bool:
    """Interactive permission prompt for tool execution."""
    preview = str(args).replace("\n", "\\n")[:100]
    print(f"  \033[33mTool {name} needs permission:\033[0m {preview}")
    try:
        answer = input("  Allow? (y/n) ").strip().lower()
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


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


async def _handle_slash(cmd: str, state=None) -> bool:
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

    if name == "/memory":
        if len(parts) > 1 and parts[1] in ("on", "enable"):
            if state is not None:
                state.auto_memory = True
                state._memory_extracted = False
                if state.memory_store:
                    state.memory_store.set_enabled(True)
            print("  \033[32mAuto-memory enabled (persisted).\033[0m")
            return False
        if len(parts) > 1 and parts[1] in ("off", "disable"):
            if state is not None:
                state.auto_memory = False
                if state.memory_store:
                    state.memory_store.set_enabled(False)
            print("  \033[33mAuto-memory disabled (persisted).\033[0m")
            return False
        if len(parts) > 1 and parts[1] in ("aggressive", "every"):
            if state is not None:
                state.memory_interval = 1
                print("  \033[33mMemory: aggressive mode (extract every turn).\033[0m")
            return False
        if len(parts) > 1 and parts[1] in ("throttle", "throttled"):
            if state is not None:
                state.memory_interval = 3
                print("  \033[2mMemory: throttled mode (extract every 3 turns).\033[0m")
            return False
        if len(parts) > 1 and parts[1] in ("list", "ls", "show"):
            from general_agent.memory.store import MemoryStore
            store = MemoryStore()
            memories = store.list_all()
            if not memories:
                print("  (no memories saved)")
            else:
                print("  \033[1mMemories:\033[0m")
                for m in memories:
                    print(f"    - {m['name']} ({m['size']}B)")
            return False
        if len(parts) > 1 and parts[1] in ("refresh", "reload"):
            memory_text = MemoryStore().format_for_prompt()
            if state is not None:
                state.system_prompt_extra = memory_text
            print("  \033[2mMemories refreshed.\033[0m")
            return False
        print("""
  /memory list     Show saved memories
  /memory refresh  Reload memories from disk
  /memory save     Ask the agent to save memories

  To save memories: just ask the agent directly,
  e.g. \"remember that I prefer TypeScript over JavaScript\".
  The agent will write to .claude/memory/.
""")
        return False

    if name == "/coordinator":
        if len(parts) > 1 and parts[1] in ("off", "disable"):
            if state is not None:
                state.system_prompt_extra = ""
                state.auto_memory = memory_store.is_enabled()
            print("  \033[33mCoordinator mode disabled.\033[0m")
            return False
        if state is not None:
            from general_agent.tasks.coordinator import COORDINATOR_SYSTEM_PROMPT
            state.system_prompt_extra = COORDINATOR_SYSTEM_PROMPT
            state.auto_memory = False
            print("  \033[32mCoordinator mode enabled.\033[0m")
            print("  \033[2mThe agent will now orchestrate workers for complex tasks.\033[0m")
            print("  \033[2mUse /coordinator off to disable.\033[0m")
        return False

    if name == "/compact":
        if state is not None:
            from general_agent.compact.compact import compact_conversation, build_post_compact_messages
            try:
                result = await compact_conversation(state.messages, state, is_auto=False)
                boundary, summary_msgs = build_post_compact_messages(result)
                state.messages = summary_msgs
                print(f"  Compressed {result.messages_summarized} messages "
                      f"({result.pre_compact_tokens} → ~{result.post_compact_tokens} tokens)")
            except Exception as e:
                print(f"  \033[31mCompact failed: {e}\033[0m")
        return False

    if name == "/autocompact":
        if len(parts) > 1 and parts[1].isdigit():
            pct = int(parts[1])
            if state is not None:
                state.compact_pct = min(99, max(10, pct))
            print(f"  \033[32mAuto-compact: {state.compact_pct}%\033[0m "
                  f"(~{int(1000000*state.compact_pct/100)} tokens)")
        else:
            print(f"  /autocompact <N>  Set auto-compact threshold "
                  f"(current: {state.compact_pct if state else 91}%)")
        return False

    if name == "/snip":
        if len(parts) > 1 and parts[1].isdigit():
            pct = int(parts[1])
            if state is not None:
                state.snip_pct = min(99, max(10, pct))
            print(f"  \033[33mSnip: {state.snip_pct}%\033[0m "
                  f"(~{int(1000000*state.snip_pct/100)} tokens)")
        else:
            print(f"  /snip <N>  Set snip threshold "
                  f"(current: {state.snip_pct if state else 80}%)")
        return False

    if name == "/context":
        if len(parts) > 1:
            size_str = parts[1].lower().rstrip("k").rstrip("K")
            if size_str.isdigit():
                k = int(size_str)
                new_window = k * 1000
                import general_agent.constants.models as cm
                cm.MODEL_CONTEXT_WINDOW = new_window
                cpct = state.compact_pct if state else 50
                spct = state.snip_pct if state else 80
                print(f"  Context: {k}K tokens")
                print(f"  Compact: ~{int(new_window*cpct/100)} tokens ({cpct}%)")
                print(f"  Snip: ~{int(new_window*spct/100)} tokens ({spct}%)")
                return False
        print(f"  /context <N>[k]  Set context window (e.g. /context 1000 or /context 1000k)")
        from general_agent.constants.models import MODEL_CONTEXT_WINDOW
        print(f"  Current: {int(MODEL_CONTEXT_WINDOW/1000)}K")
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

    if name == "/sandbox":
        if len(parts) > 1:
            if parts[1] in ("on", "enable"):
                from general_agent.sandbox.settings import toggle_sandbox
                from general_agent.sandbox.checker import is_sandbox_available
                toggle_sandbox(True)
                avail = is_sandbox_available()
                print(f"  Sandbox: \033[32mON\033[0m" + (" (unavailable on this platform)" if not avail else ""))
                return False
            if parts[1] in ("off", "disable"):
                from general_agent.sandbox.settings import toggle_sandbox
                toggle_sandbox(False)
                print(f"  Sandbox: \033[33mOFF\033[0m")
                return False
            if parts[1] in ("exclude", "add"):
                if len(parts) > 2:
                    from general_agent.sandbox.settings import get_settings
                    get_settings().excluded_commands.append(parts[2])
                    print(f"  Excluded: {parts[2]}")
                return False
        from general_agent.sandbox.settings import get_settings, is_sandbox_available
        s = get_settings()
        print(f"  /sandbox on/off    Toggle sandbox")
        print(f"  /sandbox exclude <pattern>  Add exclusion")
        print(f"  Status: {'ON' if s.enabled else 'OFF'}, "
              f"Platform: {'available' if is_sandbox_available() else 'unavailable'}, "
              f"Excluded: {s.excluded_commands[:5]}")
        return False

    if name == "/clear":
        if state is not None:
            state.messages.clear()
        print("  \033[2mConversation history cleared.\033[0m")
        return False

    if name == "/session":
        from general_agent.bootstrap.state import get_session_id, get_total_cost_usd
        print(f"  Session: {get_session_id()}")
        print(f"  Cost:    ${get_total_cost_usd():.4f}")
        return False

    print(f"  Unknown command: {name}. Type /help for available commands.")
    return None  # Let caller check skills


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
