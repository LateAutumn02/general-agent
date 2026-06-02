"""Textual TUI for general-agent.  Layout: StatusBar / Chat / PromptInput.

Adapted from TunaCode's app.py to work with our ``loop.run_agent()``.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING, Any

from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Input, LoadingIndicator, OptionList, Static
from textual.widgets.option_list import Option
from textual.screen import ModalScreen

from general_agent.bootstrap.state import get_main_loop_model, get_session_id, get_total_cost_usd
from general_agent.ui.autocomplete import CommandAutoComplete
from general_agent.ui.bridge import (
    PermissionRequest,
    ProgressMessage,
    RequestBridge,
    StreamChunk,
    StreamEnd,
    ToolDisplayMessage,
)
from general_agent.ui.streaming import StreamingHandler
from general_agent.ui.widgets.chat import ChatContainer, PanelMeta
from general_agent.ui.widgets.editor import EditorSubmitRequested, PromptInput
from general_agent.ui.widgets.messages import (
    CompactionStatusChanged,
    SystemNoticeDisplay,
)
from general_agent.ui.widgets.status_bar import StatusBar

if TYPE_CHECKING:
    from general_agent.agent.loop import AgentState
    from general_agent.memory.store import MemoryStore
    from general_agent.skills.loader import SkillInfo
    from general_agent.tools.registry import ToolsRegistry

# -- model display names -------------------------------------------

MODEL_DISPLAY_NAMES: dict[str, str] = {
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "deepseek-chat": "DeepSeek Chat",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "claude-opus-4-7": "Claude Opus 4.7",
}

# -- styles --------------------------------------------------------

STYLE_PRIMARY = "bold cyan"
STYLE_SUCCESS = "bold green"
STYLE_WARNING = "bold yellow"
STYLE_ERROR = "bold red"
STYLE_MUTED = "dim"


class TextualAgentApp(App[None]):
    """Hosts the general-agent REPL inside a Textual TUI."""

    TITLE = "general-agent"
    CSS_PATH = ["styles/layout.tcss", "styles/panels.tcss"]

    BINDINGS = [
        Binding("escape", "cancel_request", "Cancel", show=False, priority=True),
        Binding("ctrl+c", "copy_or_exit", "", show=False, priority=True),
    ]

    STREAM_THROTTLE_MS = 100.0

    def __init__(
        self,
        *,
        state: AgentState,
        registry: ToolsRegistry,
        git_context: str = "",
        memory_store: MemoryStore | None = None,
        skills: list[SkillInfo] | None = None,
        skill_cmds: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self.agent_state = state
        self.tool_registry = registry
        self.git_context = git_context
        self.memory_store = memory_store
        self.skills = skills or []
        self.skill_cmds = skill_cmds or {}

        # -- runtime ---------------------------------------------------
        self._request_queue: asyncio.Queue[str] = asyncio.Queue()
        self._processing = False
        self._pending_permission: tuple | None = None
        self._permission_allow_always: set[str] = set()
        self._streaming: StreamingHandler | None = None
        self._request_start: float = 0.0

    # -- layout ----------------------------------------------------

    def compose(self) -> ComposeResult:
        self.status_bar = StatusBar()
        self.chat_container = ChatContainer(id="chat-container")
        self.loading = LoadingIndicator()
        self._streaming_widget = Static("", id="streaming-output")
        self._streaming = StreamingHandler(self._streaming_widget, self.STREAM_THROTTLE_MS)
        self.editor = PromptInput()

        yield self.status_bar
        with Container(id="viewport"):
            yield self.chat_container
            yield self.loading
            yield self._streaming_widget
        yield self.editor
        yield CommandAutoComplete(self.editor)

    # -- lifecycle -------------------------------------------------

    def on_mount(self) -> None:
        self._show_banner()
        self._refresh_status_bar()
        self.editor.focus()
        # start the background request worker
        self.run_worker(self._request_worker(), exclusive=False, name="request_worker")

    # -- input handling --------------------------------------------

    async def on_editor_submit_requested(self, message: EditorSubmitRequested) -> None:
        user_text = message.text

        # slash commands
        if user_text.startswith("/"):
            if await self._handle_slash(user_text):
                return
            skill_name = user_text[1:].split()[0].lower()
            if skill_name in self.skill_cmds:
                skill = self.skill_cmds[skill_name]
                self.agent_state.messages.append({"role": "user", "content": skill.prompt})
                user_text = f"Execute skill: {skill.name}"
                self._write_info(f"Skill '{skill.name}' activated.")
            else:
                self._write_info(f"Unknown command: '{skill_name}'  (type /help for available commands)")
                return

        # display user message on screen
        self._write_user_message(user_text)

        # push to conversation
        self.agent_state.messages.append({"role": "user", "content": user_text})

        # defer agent processing until after next refresh — ensures
        # the user message widget is rendered before run_agent() starts
        self.call_after_refresh(self._queue_request, user_text)

    # -- request worker --------------------------------------------

    def _queue_request(self, text: str) -> None:
        """Enqueue a user message for processing (called after render refresh)."""
        self._request_queue.put_nowait(text)

    async def _request_worker(self) -> None:
        """Background worker that serially processes user requests."""
        while True:
            message_text = await self._request_queue.get()
            try:
                await self._process_request(message_text)
            except Exception as exc:
                self._write_error(f"Error: {exc}")
            finally:
                self._request_queue.task_done()

    async def _process_request(self, _message_text: str) -> None:
        """Run the agent loop with UI callbacks wired through RequestBridge."""
        from general_agent.agent.loop import run_agent

        # ---- show loading ----
        self._processing = True
        self._request_start = time.monotonic()
        self.loading.add_class("active")

        bridge = RequestBridge(self)

        try:
            result_text, all_messages = await run_agent(
                self.agent_state,
                on_text=bridge.on_text,
                on_progress=bridge.on_progress,
                on_permission=bridge.on_permission,
            )

            # ---- finalise streaming ----
            if self._streaming:
                self._streaming.flush()
                self._streaming.reset()

            # ---- write final agent response into chat ----
            final_response = self._extract_final_response(all_messages)
            result_is_error = bool(
                result_text and result_text.lstrip().lower().startswith(("error", "agent stopped"))
            )
            if result_is_error:
                self._write_error(result_text)
            elif final_response:
                self._write_agent_response(final_response)
            elif result_text and result_text.strip():
                self._write_agent_response(result_text)

        except asyncio.CancelledError:
            self._write_error("Request worker was cancelled.")
            raise
        except Exception as exc:
            self._write_error(f"{type(exc).__name__}: {exc}")
        finally:
            self.loading.remove_class("active")
            self._processing = False
            self._refresh_status_bar()

    def _copy_selection_to_clipboard(self) -> bool:
        """Copy selected TUI text, if any, without treating Ctrl+C as quit."""
        try:
            selected = self.screen.get_selected_text()
        except Exception:
            selected = None

        if not selected:
            return False

        self.copy_to_clipboard(selected)
        try:
            self.clear_selection()
        except Exception:
            pass
        self.notify("Copied selection", severity="information", timeout=1)
        return True

    # -- message handlers ------------------------------------------

    async def on_progress_message(self, message: ProgressMessage) -> None:
        """Tool status-line text."""
        self.loading.remove_class("active")
        self._write_info(message.text)

    def on_tool_display_message(self, message: ToolDisplayMessage) -> None:
        """Rich panel (bash output etc.) — write into chat.

        The renderable already carries its own Rich Panel border, so we
        don't apply additional CSS border chrome — just a margin for spacing.
        """
        self.loading.remove_class("active")
        self.chat_container.write(message.renderable, panel_meta=PanelMeta(css_class="chat-message"))

    def on_stream_chunk(self, message: StreamChunk) -> None:
        """Forward streaming delta to StreamingHandler."""
        self.loading.remove_class("active")
        if self._streaming:
            self._streaming.callback(message.chunk)

    def on_stream_end(self, _message: StreamEnd) -> None:
        """Streaming finished."""
        if self._streaming:
            self._streaming.flush()
            self._streaming.reset()

    async def on_permission_request(self, message: PermissionRequest) -> None:
        """Show an interactive permission prompt for tool calls."""
        self.push_screen(
            PermissionPickerScreen(message.tool_name, message.args),
            callback=self._on_permission_picked,
        )

    def _on_permission_picked(self, decision: tuple[bool, bool, str] | None) -> None:
        """Resolve the pending tool permission request."""
        pending = self._pending_permission
        if pending is None:
            return
        tool_name, _preview, event, result = pending
        allowed, remember, reason = decision or (False, False, "")
        result[0] = allowed
        self._pending_permission = None
        if allowed:
            if remember:
                self._permission_allow_always.add(tool_name)
                self._write_info(f"Allowed {tool_name}; future {tool_name} calls will skip prompts this session.")
            else:
                self._write_info(f"Allowed {tool_name}.")
        else:
            suffix = f"\nReason: {reason}" if reason else ""
            self._write_warning(f"Denied {tool_name}.{suffix}")
        event.set()

    async def on_system_notice_display(self, message: SystemNoticeDisplay) -> None:
        self._write_warning(message.notice)

    async def on_compaction_status_changed(self, message: CompactionStatusChanged) -> None:
        self.status_bar.set_compacting(message.active)

    # -- slash commands --------------------------------------------

    async def _handle_slash(self, cmd: str) -> bool:
        parts = cmd.split()
        name = parts[0].lower()

        if name in ("/exit", "/quit", "/q"):
            self.exit()
            return True

        if name == "/help":
            from rich.table import Table
            table = Table(title="Commands", show_header=False, border_style="dim", padding=(0, 1))
            table.add_column("cmd", style="bold cyan")
            table.add_column("desc", style="dim")
            for cmd, desc in [
                ("/exit, /quit  Esc×2", "Exit general-agent"),
                ("/help", "Show this help"),
                ("/model <name>", "Switch model"),
                ("/clear", "Clear conversation history"),
                ("/session", "Show session info"),
                ("/memory list", "List saved memories"),
                ("/memory on|off", "Toggle auto-memory"),
                ("/compact", "Compress conversation context"),
                ("/sandbox on|off", "Toggle sandbox"),
                ("/resume", "Resume a previous session"),
            ]:
                table.add_row(cmd, desc)
            self.chat_container.write(table)
            return True

        if name == "/resume":
            await self._do_resume()
            return True

        if name == "/model":
            if len(parts) > 1:
                from general_agent.bootstrap.state import set_main_loop_model
                set_main_loop_model(parts[1])
                self._refresh_status_bar()
                self._write_info(f"Model switched to {parts[1]}")
            else:
                self._write_info(f"Current model: {get_main_loop_model()}")
            return True

        if name == "/clear":
            self.agent_state.messages.clear()
            self.chat_container.clear()
            self._show_banner()
            return True

        if name == "/session":
            sid = get_session_id()
            cost = get_total_cost_usd()
            self._write_info(f"Session: {sid[:8]}...\nCost: ${cost:.4f}")
            return True

        if name == "/memory":
            return self._handle_memory_cmd(parts)

        if name == "/compact":
            await self._do_compact()
            return True

        if name == "/sandbox":
            return self._handle_sandbox_cmd(parts)

        return False

    # -- helpers ---------------------------------------------------

    def _write_user_message(self, text: str) -> None:
        """Display the user's message in the chat."""
        render_width = max(1, self.chat_container.size.width - 2)
        msg = Text()
        msg.append(f"│ {text}\n", style=STYLE_PRIMARY)
        msg.append("│ you", style=f"dim {STYLE_PRIMARY}")
        self.chat_container.write(msg, panel_meta=PanelMeta(css_class="user-message"))

    def _write_agent_response(self, text: str) -> None:
        """Write the final agent response as markdown into chat."""
        if not text.strip():
            return
        md = Markdown(text)
        self.chat_container.write(md, panel_meta=PanelMeta(css_class="agent-response"))

    def _render_resumed_context(self, messages: list[dict]) -> None:
        """Render restored conversation messages back into the chat pane."""
        for msg in messages:
            role = msg.get("role", "")
            text = self._content_to_display_text(msg.get("content", ""))
            if not text.strip():
                continue
            if role == "user":
                self._write_user_message(text)
            elif role == "assistant":
                self._write_agent_response(text)
            elif role == "system":
                self._write_info(text)
            else:
                self._write_info(f"{role or 'message'}: {text}")

    @staticmethod
    def _content_to_display_text(content: Any) -> str:
        """Convert API content blocks into readable transcript text."""
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return str(content) if content is not None else ""

        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                parts.append(str(block))
                continue
            block_type = block.get("type")
            if block_type == "text":
                parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                name = block.get("name", "tool")
                tool_input = block.get("input", {})
                parts.append(f"[tool use] {name}: {tool_input}")
            elif block_type == "tool_result":
                result = block.get("content", "")
                parts.append(f"[tool result] {TextualAgentApp._content_to_display_text(result)}")
            else:
                parts.append(str(block))
        return "\n".join(p for p in parts if p)

    def _write_info(self, text: str) -> None:
        self.chat_container.write(
            Text(text, style=STYLE_MUTED),
            panel_meta=PanelMeta(css_class="info-message"),
        )

    def _write_warning(self, text: str) -> None:
        self.chat_container.write(
            Text(text, style=STYLE_WARNING),
            panel_meta=PanelMeta(css_class="system-notice"),
        )

    def _write_error(self, text: str) -> None:
        self.chat_container.write(
            Panel(Text(text, style=STYLE_ERROR), border_style="red"),
            panel_meta=PanelMeta(css_class="error-panel"),
        )

    def _show_banner(self) -> None:
        raw = get_main_loop_model()
        display = MODEL_DISPLAY_NAMES.get(raw, raw)
        sid = get_session_id()[:8]

        banner = Text()
        banner.append("   ▄▄▄▄▄▄▄   \n", style="bold cyan")
        banner.append("  ▐░░░░░░░░░░▌  ", style="bold cyan")
        banner.append("general-agent  v0.1.0\n", style="bold white")
        banner.append("  ▐░▌░▌▐░▌▐░▌\n", style="bold cyan")
        banner.append("  ▐░▌▐░▌ ▐░▌  ", style="bold cyan")
        banner.append("A general-purpose AI coding agent\n", style="bold white")
        banner.append("   ▐░░░░░░░▌   ", style="bold cyan")
        banner.append("in your terminal.\n", style="bold white")
        banner.append("    ▀▀▀▀▀▀▀   \n", style="bold cyan")
        banner.append("\n")
        banner.append(f"  Model     {display}  ·  session {sid}\n", style="dim cyan")
        banner.append(f"  CWD       {os.getcwd()}\n", style="dim cyan")
        banner.append("\n")
        banner.append("  Type a message to start, or ", style="dim")
        banner.append("/", style="bold cyan")
        banner.append(" for commands.  ", style="dim")
        banner.append("/help", style="bold cyan")
        banner.append(" to see what's available.\n", style="dim")

        self.chat_container.write(banner)

    def _refresh_status_bar(self) -> None:
        raw = get_main_loop_model()
        display = MODEL_DISPLAY_NAMES.get(raw, raw)
        cost = get_total_cost_usd()
        est = len(self.agent_state.messages) * 512
        self.status_bar.update_stats(model=display, tokens=est, max_tokens=200000, session_cost=cost)

    def _extract_final_response(self, all_messages: list[dict]) -> str:
        """Extract the last assistant text from the message history."""
        for msg in reversed(all_messages):
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content", "")
            if isinstance(content, list):
                # ContentBlock[] — collect text blocks
                texts = [b.get("text", "") for b in content if b.get("type") == "text"]
                return "\n".join(t for t in texts if t)
            if isinstance(content, str):
                return content
        return ""

    def _handle_memory_cmd(self, parts: list[str]) -> bool:
        sub = parts[1] if len(parts) > 1 else ""
        store = self.memory_store
        if not store:
            self._write_info("Memory store not available.")
            return True

        if sub in ("list", "ls", "show"):
            mems = store.list_all()
            if not mems:
                self._write_info("(no memories saved)")
            else:
                self._write_info("\n".join(f"  - {m['name']}" for m in mems))
            return True
        if sub in ("on", "enable"):
            self.agent_state.auto_memory = True
            store.set_enabled(True)
            self._write_info("Auto-memory enabled.")
            return True
        if sub in ("off", "disable"):
            self.agent_state.auto_memory = False
            store.set_enabled(False)
            self._write_info("Auto-memory disabled.")
            return True
        if sub in ("refresh", "reload"):
            self.agent_state.system_prompt_extra = store.format_for_prompt()
            self._write_info("Memories refreshed.")
            return True

        self._write_info("/memory list | on | off | refresh")
        return True

    async def _do_resume(self) -> None:
        """Show an interactive session picker."""
        try:
            from general_agent.session.discovery import list_sessions
            sessions = await list_sessions(cwd=os.getcwd(), limit=20)
            if not sessions:
                self._write_info("No previous sessions found for this project.")
                return
            self._write_info("Loading sessions…")
            self.push_screen(SessionPickerScreen(sessions), callback=self._on_session_picked)
        except Exception as e:
            self._write_error(f"Session list failed: {e}")

    async def _on_session_picked(self, picked: str | None) -> None:
        """Resume the selected session or do nothing if cancelled."""
        if picked is None:
            return
        try:
            conv, resolved_session_id, file_path = await _load_session_by_id(picked, os.getcwd())
            if not conv:
                self._write_error(f"Session {picked[:8]} could not be loaded.")
                return

            from general_agent.bootstrap.state import set_session_id
            from general_agent.session.store import get_session_store

            set_session_id(resolved_session_id)
            store = get_session_store()
            store._session_file = file_path  # noqa: SLF001
            store._message_uuids = set()  # noqa: SLF001

            self.agent_state.messages.clear()
            self.agent_state.messages.extend(conv)
            self.chat_container.clear()
            self._show_banner()
            self._write_info(f"Resumed session {resolved_session_id[:8]} ({len(conv)} messages)")
            self._render_resumed_context(conv)
            self._refresh_status_bar()
        except Exception as e:
            self._write_error(f"Resume failed: {e}")

    async def _do_compact(self) -> None:
        try:
            from general_agent.compact.compact import build_post_compact_messages, compact_conversation
            result = await compact_conversation(self.agent_state.messages, self.agent_state, is_auto=False)
            _, summary = build_post_compact_messages(result)
            self.agent_state.messages = summary
            self._write_info(
                f"Compressed {result.messages_summarized} msgs "
                f"({result.pre_compact_tokens} → ~{result.post_compact_tokens} tokens)"
            )
            self._refresh_status_bar()
        except Exception as e:
            self._write_error(f"Compact failed: {e}")

    def _handle_sandbox_cmd(self, parts: list[str]) -> bool:
        sub = parts[1] if len(parts) > 1 else ""
        if sub in ("on", "enable"):
            from general_agent.sandbox.checker import is_sandbox_available
            from general_agent.sandbox.settings import toggle_sandbox
            toggle_sandbox(True)
            avail = "" if is_sandbox_available() else " (unavailable on this platform)"
            self._write_info(f"Sandbox ON{avail}")
            return True
        if sub in ("off", "disable"):
            from general_agent.sandbox.settings import toggle_sandbox
            toggle_sandbox(False)
            self._write_info("Sandbox OFF")
            return True
        self._write_info("/sandbox on | off")
        return True

    # -- key bindings ----------------------------------------------

    def action_copy_or_exit(self) -> None:
        """Copy selected text, otherwise require a second Ctrl+C to quit."""

        if self._copy_selection_to_clipboard():
            return

        now = time.monotonic()
        last = getattr(self, "_last_ctrl_c", 0.0)
        self._last_ctrl_c = now
        if now - last < 1.0:
            self.exit()
            return

        if self._processing:
            self.notify("Press Ctrl+C again to exit. Press Esc to cancel the request.", severity="warning", timeout=2)
        else:
            self.notify("Press Ctrl+C again to exit", severity="warning", timeout=1)

    async def action_cancel_request(self) -> None:
        """Single Esc: cancel current request.  Double Esc (within 1s, idle): quit."""
        if self._processing:
            self.agent_state.abort_signal.set()
            self._write_info("Request cancelled.")
            return

        now = time.monotonic()
        last = getattr(self, "_last_esc", 0.0)
        self._last_esc = now
        if now - last < 1.0:
            self.exit()
        else:
            self.notify("Press Esc again to exit  (/exit, /quit also work)", severity="warning", timeout=1)


# ---------------------------------------------------------------------------
# Permission picker screen
# ---------------------------------------------------------------------------


class PermissionPickerScreen(ModalScreen[tuple[bool, bool, str] | None]):
    """Keyboard-first permission dialog for tool calls."""

    BINDINGS = [
        Binding("escape", "deny", "Deny", show=False),
        Binding("a", "allow", "Allow", show=False),
        Binding("d", "allow_always", "Always Allow", show=False),
        Binding("n", "deny", "Deny", show=False),
        Binding("tab", "focus_reason", "Reason", show=False),
    ]

    def __init__(self, tool_name: str, args: dict) -> None:
        super().__init__()
        self._tool_name = tool_name
        self._args = args
        self._reason_mode = False

    def compose(self) -> ComposeResult:
        preview = self._format_preview(self._args)
        options = [
            Option("── Tool permission ──", disabled=True),
            Option("Yes", id="allow"),
            Option("Yes, don't ask again", id="allow_always"),
            Option("No  [dim](Tab to tell the agent what to do differently)[/dim]", id="deny"),
        ]
        if preview:
            options.insert(1, Option(f"Request: {preview}", disabled=True))
        yield OptionList(*options, id="permission-list")
        yield Input(placeholder="Tell the agent what to do differently", id="permission-reason")

    def on_mount(self) -> None:
        ol = self.query_one(OptionList)
        ol.highlighted = 2 if self._format_preview(self._args) else 1
        ol.focus()
        self.query_one("#permission-reason", Input).display = False

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self._select(event.option_list)

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self.action_deny()

    def _select(self, ol: OptionList) -> None:
        opt = ol.get_option_at_index(ol.highlighted)
        if opt.id == "allow":
            self.dismiss((True, False, ""))
        elif opt.id == "allow_always":
            self.dismiss((True, True, ""))
        elif opt.id == "deny":
            self.dismiss((False, False, ""))

    def action_select_highlighted(self) -> None:
        self._select(self.query_one(OptionList))

    def action_allow(self) -> None:
        self.dismiss((True, False, ""))

    def action_allow_always(self) -> None:
        self.dismiss((True, True, ""))

    def action_deny(self) -> None:
        if self._reason_mode:
            reason = self.query_one("#permission-reason", Input).value.strip()
            self.dismiss((False, False, reason))
        else:
            self.dismiss((False, False, ""))

    def action_focus_reason(self) -> None:
        ol = self.query_one(OptionList)
        opt = ol.get_option_at_index(ol.highlighted)
        if opt.id == "deny":
            self._reason_mode = True
            reason = self.query_one("#permission-reason", Input)
            reason.display = True
            reason.focus()
        else:
            ol.action_cursor_down()

    @staticmethod
    def _format_preview(args: dict) -> str:
        if not args:
            return ""
        for key in ("command", "file_path", "path", "url", "pattern"):
            value = args.get(key)
            if isinstance(value, str) and value:
                text = value.replace("\n", " ")
                return text[:120] + ("..." if len(text) > 120 else "")
        text = str(args).replace("\n", " ")
        return text[:120] + ("..." if len(text) > 120 else "")


# ---------------------------------------------------------------------------
# Session picker screen
# ---------------------------------------------------------------------------


class SessionPickerScreen(ModalScreen[str | None]):
    """Modal screen that lets the user pick a session with arrow keys / numbers.

    Returns the selected ``session_id`` or ``None`` (cancelled).
    """

    BINDINGS = [
        Binding("escape", "dismiss_none", "Cancel", show=True),
        Binding("enter", "select_highlighted", "Select", show=True),
    ]

    def __init__(self, sessions: list) -> None:
        super().__init__()
        self._sessions = sessions

    def compose(self) -> ComposeResult:
        from datetime import datetime
        options: list[Option] = []
        for i, s in enumerate(self._sessions):
            ts = datetime.fromtimestamp(s.last_modified).strftime("%m-%d %H:%M") if s.last_modified else "?"
            preview = (s.summary or s.first_prompt or "")[:60]
            label = f"[{i + 1}]  {s.session_id[:8]}  {ts}  {preview}"
            options.append(Option(label, id=s.session_id))
        options.insert(0, Option("── Sessions (↑↓ or number, Enter to resume, Esc to cancel) ──", disabled=True))
        yield OptionList(*options, id="session-list")

    def on_mount(self) -> None:
        ol = self.query_one(OptionList)
        if len(self._sessions) > 0:
            ol.highlighted = 1  # skip the header line
        ol.focus()

    def on_key(self, event: events.Key) -> None:
        if event.key and event.key.isdigit():
            n = int(event.key)
            if n == 0:
                n = 10
            ol = self.query_one(OptionList)
            if 0 < n < len(ol.option_count):
                ol.highlighted = n
                self._select(ol)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self._select(event.option_list)

    def _select(self, ol: OptionList) -> None:
        opt = ol.get_option_at_index(ol.highlighted)
        if opt.id:
            self.dismiss(opt.id)

    def action_select_highlighted(self) -> None:
        ol = self.query_one(OptionList)
        self._select(ol)

    def action_dismiss_none(self) -> None:
        self.dismiss(None)


async def _load_session_by_id(session_id: str, cwd: str) -> tuple[list[dict], str, str]:
    """Load conversation messages from a session file."""
    import os as _os
    from general_agent.session.discovery import list_sessions
    from general_agent.session.store import get_project_dir, get_session_store

    sessions = await list_sessions(cwd=cwd, limit=100)
    for s in sessions:
        if s.session_id == session_id or s.session_id.startswith(session_id):
            path = _os.path.join(get_project_dir(cwd), f"{s.session_id}.jsonl")
            result = await get_session_store().load_transcript(path)
            msgs = result.get("messages", [])
            conv: list[dict] = []
            for m in msgs:
                inner = m.get("message", m)
                role = inner.get("role", m.get("type", ""))
                entry: dict[str, Any] = {
                    "role": role,
                    "content": inner.get("content", ""),
                }
                if role == "assistant":
                    if "usage" in inner:
                        entry["usage"] = inner["usage"]
                    if "stop_reason" in inner:
                        entry["stop_reason"] = inner["stop_reason"]
                conv.append(entry)
            return conv, s.session_id, path
    return [], "", ""
