# Bash UI Transcript Display

> Last updated: 2026-06-17 | Reference: user-provided Codex CLI transcript style

The main TUI transcript uses a compact Codex-style stream. It should stay readable while tools run, and it should not let verbose tool output occupy the whole screen.

## Rendering Rules

1. **Assistant messages** - render each assistant turn as a bullet block that starts with `• `, followed by the assistant text.
2. **Tool progress** - render non-approval tool calls as one bullet summary, such as `• Searched the web for SAM 3 paper Segment Anything Model 3`.
3. **Tool result renderables** - treat Rich panels and tables as data sources. Convert them to plain text, keep only the first useful summary line, and avoid showing bulky stdout/stderr in the main transcript.
4. **Separators** - insert a dim horizontal rule `─────────────────────────────────────` between transcript messages.
5. **Approval UI** - show permission prompts in the bottom interaction area, not at the top of the transcript, using the same background as the input area.

## Scope

This policy applies to the default chat screen. Background task detail views may keep a denser inspection-oriented layout, but they should not block the main chat from staying compact.
