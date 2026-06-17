# general-agent

This repository is being rebuilt as a TypeScript-first agent project.

The previous Python implementation has been archived under `legacy/python/` so the history and design notes stay available while the new implementation starts from a clean root.

## Current Direction

- Runtime: TypeScript + Bun
- Primary interface: terminal UI
- UI goal: polished, compact, keyboard-first agent experience
- Legacy reference: `legacy/python/`

## Next Steps

See `docs/refactor/typescript-rewrite-plan.md` for the migration plan.

## Run The Rewrite Preview

```bash
bun install
bun run start
```

The current preview is a TUI scaffold. It supports normal input, `!` bash mode detection, `/help`, and `/exit`.
