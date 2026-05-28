"""System and user context gathered at startup.

Matching cc-haha src/context.ts pattern:
- get_system_context(): git status, branch, recent commits (memoized)
- get_user_context(): CLAUDE.md / memory files (stub for Phase 2)

Reference: cc-haha src/context.ts, initialization/flow.md 阶段9
"""

from __future__ import annotations

import functools
import subprocess
from dataclasses import dataclass


@dataclass
class SystemContext:
    """Git state gathered at session start."""
    branch: str = ""
    default_branch: str = ""
    git_status: str = ""
    recent_commits: str = ""
    git_user: str = ""
    cwd: str = ""


@functools.lru_cache(maxsize=1)
def get_system_context(cwd: str) -> SystemContext:
    """Gather git context (memoized per cwd).

    Runs 5 parallel git commands, matching cc-haha pattern.
    Truncates git status at 2000 chars.
    """
    ctx = SystemContext(cwd=cwd)

    def _git(args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    # 5 parallel calls (sequential for simplicity in v1)
    ctx.branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    ctx.default_branch = _git(["remote", "show", "origin"]) or _get_default_branch_fallback(ctx)

    status = _git(["status", "--short"])
    ctx.git_status = status[:2000] if len(status) > 2000 else status

    ctx.recent_commits = _git(["log", "--oneline", "-n", "5"])
    ctx.git_user = _git(["config", "user.name"])

    return ctx


def _get_default_branch_fallback(ctx: SystemContext) -> str:
    """Fallback: check if main or master exists as a branch."""
    import os
    head_path = os.path.join(ctx.cwd, ".git", "refs", "heads")
    for branch in ("main", "master"):
        if os.path.exists(os.path.join(head_path, branch)):
            return branch
    return "main"


@functools.lru_cache(maxsize=1)
def get_user_context(cwd: str) -> str:
    """Gather CLAUDE.md / memory content (stub for Phase 2).

    Returns:
        Empty string for now - Phase 2 will walk directory tree
        for CLAUDE.md and MEMORY.md files.
    """
    # TODO: Phase 2 - walk directory tree, read CLAUDE.md / MEMORY.md
    return ""


def format_system_context(ctx: SystemContext) -> str:
    """Format system context as a prompt section.

    Matching cc-haha's injection format.
    """
    parts = []

    if ctx.branch:
        parts.append(f"<git_status>")
        parts.append(f"This is the git status at the start of the conversation. "
                     f"Note that this status is a snapshot in time, and will not "
                     f"update during the conversation.")
        if ctx.branch and ctx.default_branch:
            parts.append(f"On branch {ctx.branch}")
            parts.append(f"Main branch (you will usually use this for PRs): "
                         f"{ctx.default_branch}")
        parts.append(f"Current branch: {ctx.branch}")
        parts.append(f"")
        if ctx.git_status:
            parts.append(ctx.git_status)
        if ctx.recent_commits:
            parts.append(f"")
            parts.append(f"Recent commits:")
            parts.append(ctx.recent_commits)
        parts.append(f"</git_status>")

    return "\n".join(parts)
