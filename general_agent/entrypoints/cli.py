"""CLI entry point - fast-path dispatch then full CLI.

Mimics cc-haha src/entrypoints/cli.tsx pattern:
- Fast-path handlers for special flags (--version, --help, etc.)
- Fallthrough to main() for the interactive/REPL path.
- Module-level side effects run before main().

Reference: cc-haha src/entrypoints/cli.tsx
"""

from __future__ import annotations

import asyncio
import os
import sys

from general_agent.ui.render import separator

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
        "  --model, -m MODEL  Model to use (set via config or env)\n"
        "  --print, -p        Non-interactive mode, output result and exit\n"
        "  --continue, -c     Continue the most recent session\n"
        "  --verbose          Enable debug logging\n"
        "  --permission-mode MODE  Permission mode (default|acceptEdits|bypassPermissions)\n"
        "\n"
        "Environment:\n"
        "  API_KEY  API key (required)\n"
        "  MODEL  Model name override\n"
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
        os.environ["SIMPLE"] = "1"

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
    parser.add_argument("--model", "-m", default=os.environ.get("MODEL", ""))
    parser.add_argument("--print", "-p", action="store_true", default=False)
    parser.add_argument("--continue", "-c", dest="continue_session", action="store_true", default=False)
    parser.add_argument("--verbose", action="store_true", default=False)
    parser.add_argument("--permission-mode", default="default")
    parser.add_argument("--bare", action="store_true", default=False)

    args = parser.parse_args(argv)

    # Build config from CLI args
    from general_agent.bootstrap.init import AppConfig

    _api_key = os.environ.get("API_KEY", "")
    config = AppConfig(
        api_key=_api_key,
        model=args.model or os.environ.get("MODEL", ""),
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
            max_turns=10,
        )
        # Stream text to stdout in print mode
        result_text, _ = await run_agent(state, on_permission=lambda n, a: True,
                                          on_text=lambda t: _print_chunk(t),
                                          on_progress=lambda m: print(m, flush=True))
        if result_text and ("Error" in result_text or "stopped" in result_text.lower()):
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
            max_turns=10,
        )
        result_text, all_msgs = await run_agent(state, on_permission=lambda n, a: True,
                                                  on_text=lambda t: _print_chunk(t),
                                                  on_progress=lambda m: print(m, flush=True))
        for msg in reversed(all_msgs):
            if msg.get("role") == "assistant":
                _print_assistant_usage(msg)
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
            API_KEY=api_key,
            BASE_URL=base_url,
            MODEL=model,
            PROVIDER="anthropic",
        )
    else:
        # OpenAI-compatible
        default_url = "https://api.deepseek.com"
        base_url = input(f"  Base URL [{default_url}]: ").strip() or default_url
        api_key = input("  API Key: ").strip()
        _save_env(
            API_KEY=api_key,
            BASE_URL=base_url,
            MODEL=model,
            PROVIDER="openai",
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

    # ── Rich REPL ──
    try:
        while True:
            print()
            separator()
            try:
                user_input = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            separator()

            if not user_input:
                continue

            if readline is not None:
                readline.write_history_file(hist_file)

            if user_input.startswith("/"):
                result = await _handle_slash(user_input, state)
                if result:
                    break
                if result is not None:
                    continue
                skill_name = user_input[1:].split()[0].lower()
                if skill_name in skill_cmds:
                    skill = skill_cmds[skill_name]
                    state.messages.append({"role": "user", "content": skill.prompt})
                    state.messages.append({"role": "user", "content": f"Execute the skill: {skill.name}"})
                    print(f"  [2mSkill '{skill.name}' activated.[0m")
                    result_text, all_messages = await run_agent(
                        state, on_progress=lambda msg: print(msg, flush=True))
                    for msg in reversed(all_messages):
                        if msg.get("role") == "assistant":
                            _print_assistant_response(msg)
                            break
                    continue
                continue

            state.messages.append({"role": "user", "content": user_input})

            _spinner: asyncio.Task | None = None
            _first_text = True
            _had_tools = False
            _had_stream_text = False

            def _on_text(chunk: str) -> None:
                nonlocal _first_text, _spinner, _had_stream_text
                _had_stream_text = True
                if _first_text:
                    _first_text = False
                    if _spinner: _spinner.cancel()
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                sys.stdout.write(chunk)
                sys.stdout.flush()

            def _on_progress(msg: str) -> None:
                nonlocal _first_text, _spinner, _had_tools
                _had_tools = True
                if _first_text:
                    _first_text = False
                    if _spinner: _spinner.cancel()
                sys.stdout.write("\n")
                sys.stdout.flush()
                # msg is raw ANSI text from render.py, print directly
                print(msg, flush=True)

            try:
                import time as _t; _start = _t.monotonic()
                _spinner = asyncio.create_task(_spin(None, "medium", _start))

                result_text, all_messages = await run_agent(
                    state,
                    on_text=_on_text,
                    on_progress=_on_progress,
                    on_permission=_ask_permission)

                if _spinner: _spinner.cancel()
                elapsed = _t.monotonic() - _start
                if not _first_text:
                    line = f"  \033[2mThought for {elapsed:.0f}s\033[0m"
                    # Pad to clear any leftover spinner characters
                    sys.stdout.write(f"\r{line.ljust(60)}\n")
                    sys.stdout.flush()
                    if _had_tools and not _had_stream_text:
                        print("  \033[2mDone\033[0m", flush=True)

                if result_text and "stopped" in result_text.lower():
                    print(f"  \033[1;31m! {result_text}\033[0m", flush=True)

                for msg in reversed(all_messages):
                    if msg.get("role") == "assistant":
                        _print_assistant_usage(msg)
                        break

            except Exception as e:
                if _spinner:
                    try: _spinner.cancel()
                    except Exception: pass
                print(f"\n  \033[1;31mError: {e}\033[0m\n", flush=True)

    finally:
        try:
            if memory_store and memory_store.is_enabled():
                memory_store.save()
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

    display_model = get_main_loop_model()
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
    /resume         Resume a previous session
    /session        Show session info
    /compact        Manually compact conversation context
    /memory         Manage auto-memory (on/off/list)
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
        from general_agent.bootstrap.state import get_session_id
        print(f"  Session: {get_session_id()}")
        return False

    if name == "/resume":
        await _cmd_resume(state)
        return False

    print(f"  Unknown command: {name}. Type /help for available commands.")
    return None  # Let caller check skills


async def _cmd_resume(state) -> None:
    """Resume a previous session: list recent sessions and restore one."""
    import os as _os
    from general_agent.session.discovery import list_sessions

    cwd = _os.getcwd()
    sessions = await list_sessions(cwd=cwd, limit=10)

    if not sessions:
        print("  \033[2mNo previous sessions found for this project.\033[0m")
        return

    print(f"\n  \033[1mRecent sessions ({cwd}):\033[0m\n")
    for i, s in enumerate(sessions):
        title = s.custom_title or s.first_prompt or s.summary
        # Truncate for display
        display = title[:70] + "…" if len(title) > 70 else title
        ts = ""
        if s.last_modified:
            import datetime
            dt = datetime.datetime.fromtimestamp(s.last_modified)
            ts = dt.strftime("%m/%d %H:%M")
        print(f"  \033[2m[{i+1}]\033[0m {display}")
        tag_str = f" \033[33m#{s.tag}\033[0m" if s.tag else ""
        branch_str = f" \033[2m@{s.git_branch}\033[0m" if s.git_branch else ""
        size_kb = f"  {s.file_size//1024}KB" if s.file_size else ""
        print(f"      \033[2m{ts}{tag_str}{branch_str}{size_kb}\033[0m")

    print()
    choice = input("  Pick a session (number, or Enter to cancel): ").strip()
    if not choice or not choice.isdigit():
        return

    idx = int(choice) - 1
    if idx < 0 or idx >= len(sessions):
        print("  \033[31mInvalid choice.\033[0m")
        return

    selected = sessions[idx]

    # Build path and load transcript
    from general_agent.session.store import get_project_dir
    project_dir = get_project_dir(cwd)
    file_path = _os.path.join(project_dir, f"{selected.session_id}.jsonl")

    from general_agent.session.store import get_session_store
    store = get_session_store()
    result = await store.load_transcript(file_path)

    messages = result.get("messages", [])
    if not messages:
        print("  \033[31mCould not load messages from session.\033[0m")
        return

    # Extract conversation messages (strip session metadata envelope)
    conversation: list[dict[str, Any]] = []
    for m in messages:
        inner = m.get("message", m)
        # Clean up the entry for API compatibility
        role = inner.get("role", m.get("type", ""))
        content = inner.get("content", "")
        entry: dict[str, Any] = {"role": role, "content": content}
        # Preserve usage and stop_reason for assistant messages
        if role == "assistant":
            if "usage" in inner:
                entry["usage"] = inner["usage"]
            if "stop_reason" in inner:
                entry["stop_reason"] = inner["stop_reason"]
        conversation.append(entry)

    # Switch session ID and replace messages
    from general_agent.bootstrap.state import set_session_id
    set_session_id(selected.session_id)

    # Re-materialize the session file so subsequent writes go to the same file
    store._session_file = file_path  # noqa: SLF001
    store._message_uuids = set()  # noqa: SLF001 — reset dedup for resumed session

    if state is not None:
        state.messages = conversation

    print(f"  \033[32mResumed session {selected.session_id[:8]} "
          f"({len(conversation)} messages)\033[0m")
    print(f"  \033[2mLast: {selected.summary[:60]}\033[0m")


def _print_assistant_usage(msg: dict[str, Any]) -> None:
    """Print only token usage (text was already streamed)."""
    usage = msg.get("usage", {})
    if usage:
        input_t = usage.get("input_tokens", 0)
        output_t = usage.get("output_tokens", 0)
        if input_t or output_t:
            print(f"\n  \033[2mTokens: {input_t} in / {output_t} out\033[0m")


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
            print(f"\n  \033[2mTokens: {input_t} in / {output_t} out\033[0m")


def _print_chunk(text: str) -> None:
    """Print a streamed text chunk immediately without buffering."""
    sys.stdout.write(text)
    sys.stdout.flush()


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


# ── Spinner & thinking helpers ──

_SPINNER = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_EFFORT_STYLE = {"low": "[dim]low[/dim]", "medium": "", "high": "[bold]high[/bold]"}


async def _spin(console, effort: str, start: float) -> None:
    """Animated spinner — low-level write for clean single-line updates."""
    import asyncio as _a
    i = 0
    label = _EFFORT_STYLE.get(effort, "medium")
    try:
        while True:
            elapsed = __import__("time").monotonic() - start
            s = _SPINNER[i % len(_SPINNER)]
            # Use raw stdout write to avoid Rich's line buffering
            sys.stdout.write(
                f"\r  \033[2m{s} Thinking… ({elapsed:.0f}s · {label})\033[0m"
            )
            sys.stdout.flush()
            i += 1
            await _a.sleep(0.15)
    except _a.CancelledError:
        # Don't clear the spinner line — _on_text already writes \n
        # before the first text chunk. Clearing here races with that
        # and wipes out the beginning of the streamed response.
        pass


def _thinking_effort(state) -> str:
    """Determine thinking effort from agent state or model config."""
    # [v1] Default "medium" — could read from model config in future
    return "medium"


def cli_main() -> None:
    """Synchronous wrapper for the async main().

    Called from __main__ guard or pyproject.toml entry point.
    """
    import asyncio

    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
