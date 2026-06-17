# TypeScript Rewrite Plan

> Last updated: 2026-06-17

## Goal

Rebuild `general-agent` as a TypeScript-first project with a polished terminal UI as the primary product surface.

The Python implementation remains archived in `legacy/python/` for reference, but new feature work should target the TypeScript rewrite.

## Principles

1. **UI first** - the terminal experience is the main value of this project, so rendering, interaction, approval flow, and session ergonomics are first-class concerns.
2. **Do not port blindly** - keep useful concepts from the Python implementation, but redesign module boundaries for TypeScript.
3. **Use references responsibly** - study external projects for behavior and interaction patterns, but implement our own project structure and code.
4. **Document before large changes** - each major module gets a short flow document before implementation.

## Proposed Structure

```text
src/
  cli/              # process entrypoints and argument parsing
  tui/              # terminal UI components and rendering
  agent/            # agent loop and model streaming
  tools/            # Bash, Read, Edit, Write, Web tools
  permissions/      # tool approval policies and prompts
  session/          # persistence, resume, transcript storage
  tasks/            # background task registry and task UI
  config/           # settings and environment loading
docs/
  refactor/         # rewrite plan and migration notes
  tui/              # UI flow and data structures
  agent/            # agent loop design
  tools/            # tool execution and display policy
legacy/
  python/           # archived Python implementation
```

## Migration Phases

1. **Scaffold** - create Bun/TypeScript project files, CLI entrypoint, and a minimal TUI shell.
2. **TUI MVP** - implement input, compact transcript, bash mode with `!`, footer status, and permission prompt mock.
3. **Tool Runtime** - implement Bash, Read, Write, Edit, and tool result formatting.
4. **Agent Loop** - connect model streaming, tool calls, permission checks, and transcript persistence.
5. **Sessions** - add resume, session listing, and full context restoration.
6. **Tasks** - add user-managed background task board.
7. **Polish** - theme, keybindings, error display, copy behavior, performance, and packaging.

## Legacy Policy

The archived Python implementation is read-only unless a fix is needed to help migration. New work should not extend `legacy/python/`.
