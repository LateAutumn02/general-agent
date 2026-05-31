"""Session discovery — list past sessions from disk.

Scans ~/.glagent/projects/ for .jsonl files, extracts metadata
from head/tail reads (avoids full file parse for large sessions).

Reference: cc-haha src/utils/listSessionsImpl.ts, sessionStoragePortable.ts
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from general_agent.session.store import (
    LITE_READ_BUF_SIZE,
    get_projects_dir,
    sanitize_path,
)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class SessionInfo:
    """Lightweight session metadata for listing.

    Reference: cc-haha listSessionsImpl.ts SessionInfo
    """
    session_id: str
    summary: str
    last_modified: float = 0.0
    file_size: int = 0
    custom_title: str | None = None
    first_prompt: str | None = None
    git_branch: str | None = None
    cwd: str | None = None
    tag: str | None = None
    created_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "summary": self.summary,
            "lastModified": self.last_modified,
            "fileSize": self.file_size,
            "customTitle": self.custom_title,
            "firstPrompt": self.first_prompt,
            "gitBranch": self.git_branch,
            "cwd": self.cwd,
            "tag": self.tag,
            "createdAt": self.created_at,
        }


# ---------------------------------------------------------------------------
# UUID validation
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _validate_uuid(s: str) -> str | None:
    return s if _UUID_RE.match(s) else None


# ---------------------------------------------------------------------------
# Head/tail JSON field extraction (no full parse needed)
# ---------------------------------------------------------------------------

def _extract_json_field(text: str, key: str) -> str | None:
    """Extract a simple JSON string field value without full parsing.

    Searches for `"key":"value"` pattern. Returns the first match.

    Reference: cc-haha sessionStoragePortable.ts extractJsonStringField()
    """
    for pattern in (f'"{key}":"', f'"{key}": "'):
        idx = text.find(pattern)
        if idx < 0:
            continue
        value_start = idx + len(pattern)
        i = value_start
        while i < len(text):
            if text[i] == "\\":
                i += 2
                continue
            if text[i] == '"':
                raw = text[value_start:i]
                try:
                    return json.loads(f'"{raw}"')
                except json.JSONDecodeError:
                    return raw
            i += 1
    return None


def _extract_last_json_field(text: str, key: str) -> str | None:
    """Like _extract_json_field but finds the LAST occurrence.

    Reference: cc-haha extractLastJsonStringField()
    """
    last_value: str | None = None
    for pattern in (f'"{key}":"', f'"{key}": "'):
        search_from = 0
        while True:
            idx = text.find(pattern, search_from)
            if idx < 0:
                break
            value_start = idx + len(pattern)
            i = value_start
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    raw = text[value_start:i]
                    try:
                        last_value = json.loads(f'"{raw}"')
                    except json.JSONDecodeError:
                        last_value = raw
                    break
                i += 1
            search_from = idx + 1
    return last_value


def _extract_first_prompt(head: str) -> str | None:
    """Extract the first meaningful user message text from transcript head.

    Tries multiple strategies:
    1. Extract direct "content" string field
    2. Extract "text" field inside content array blocks
    3. Fall back to the raw line text

    Reference: cc-haha extractFirstPromptFromHead()
    """
    lines = head.split("\n")
    for line in lines:
        if '"type":"user"' not in line and '"type": "user"' not in line:
            continue
        if '"isSidechain":true' in line or '"isSidechain": true' in line:
            continue
        if '"isMeta":true' in line or '"isMeta": true' in line:
            continue
        if '"isCompactSummary":true' in line:
            continue
        # Strategy 1: direct content string field from "message":{"content":"..."}
        text = _extract_json_field(line, "content")
        if text and text.strip() and not text.startswith("[{"):
            flat = text.replace("\n", " ").strip()
            return flat[:200] + "…" if len(flat) > 200 else flat
        # Strategy 2: text field inside content array block
        text = _extract_json_field(line, "text")
        if text and text.strip():
            flat = text.replace("\n", " ").strip()
            return flat[:200] + "…" if len(flat) > 200 else flat
    return None


# ---------------------------------------------------------------------------
# Lite file read (head + tail only)
# ---------------------------------------------------------------------------

def _read_file_lite(file_path: str) -> dict[str, Any] | None:
    """Read head and tail of a session file without loading the whole thing.

    Returns: dict with head, tail, mtime, size — or None on error.

    Reference: cc-haha sessionStoragePortable.ts readSessionLite()
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return None
        stat = path.stat()
        size = stat.st_size
        mtime = stat.st_mtime

        with open(file_path, "rb") as f:
            if size <= LITE_READ_BUF_SIZE * 2:
                # Small file — read entirely
                data = f.read().decode("utf-8", errors="replace")
                return {
                    "head": data,
                    "tail": data,
                    "mtime": mtime,
                    "size": size,
                }
            # Read head
            f.seek(0)
            head = f.read(LITE_READ_BUF_SIZE).decode("utf-8", errors="replace")
            # Read tail
            f.seek(max(0, size - LITE_READ_BUF_SIZE))
            tail = f.read(LITE_READ_BUF_SIZE).decode("utf-8", errors="replace")

        return {"head": head, "tail": tail, "mtime": mtime, "size": size}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Parse SessionInfo from lite read
# ---------------------------------------------------------------------------

def _parse_session_info(
    session_id: str,
    lite: dict[str, Any],
    project_path: str | None = None,
) -> SessionInfo | None:
    """Extract SessionInfo fields from a lite file read.

    Reference: cc-haha listSessionsImpl.ts parseSessionInfoFromLite()
    """
    head = lite["head"]
    tail = lite["tail"]

    # Skip sidechain sessions
    first_newline = head.find("\n")
    first_line = head[:first_newline] if first_newline >= 0 else head
    if '"isSidechain":true' in first_line or '"isSidechain": true' in first_line:
        return None

    # Extract fields
    custom_title = (
        _extract_last_json_field(tail, "customTitle")
        or _extract_json_field(head, "customTitle")
        or None
    )
    first_prompt = _extract_first_prompt(head) or None
    # Created at from first entry timestamp
    first_ts = _extract_json_field(head, "timestamp")
    created_at = None
    if first_ts:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            created_at = dt.timestamp()
        except (ValueError, OSError):
            pass

    summary = custom_title or first_prompt or "No prompt"

    git_branch = (
        _extract_last_json_field(tail, "gitBranch")
        or _extract_json_field(head, "gitBranch")
        or None
    )
    session_cwd = _extract_json_field(head, "cwd") or project_path or None

    # Tag: only from {"type":"tag"} entry lines (avoid tool_use input collision)
    tag = None
    for line in reversed(tail.split("\n")):
        if line.startswith('{"type":"tag"'):
            tag = _extract_json_field(line, "tag") or None
            break

    return SessionInfo(
        session_id=session_id,
        summary=summary,
        last_modified=lite["mtime"],
        file_size=lite["size"],
        custom_title=custom_title,
        first_prompt=first_prompt,
        git_branch=git_branch,
        cwd=session_cwd,
        tag=tag,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# List sessions
# ---------------------------------------------------------------------------

async def list_sessions(
    cwd: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[SessionInfo]:
    """List recent sessions, optionally filtered by project directory.

    Args:
        cwd: If provided, only return sessions for this project directory.
        limit: Max sessions to return.
        offset: Number of sessions to skip (for pagination).

    Returns:
        Sorted list of SessionInfo (newest first by last_modified).

    Reference: cc-haha listSessionsImpl()
    """
    projects_dir = get_projects_dir()
    if not os.path.isdir(projects_dir):
        return []

    candidates: list[tuple[str, str]] = []  # (session_id, file_path)

    if cwd is not None:
        # Look in specific project directory
        project_dir = os.path.join(projects_dir, sanitize_path(cwd))
        candidates = _scan_project_dir(project_dir)
    else:
        # Look in all project directories
        try:
            for dirname in os.listdir(projects_dir):
                dirpath = os.path.join(projects_dir, dirname)
                if os.path.isdir(dirpath):
                    candidates.extend(_scan_project_dir(dirpath))
        except OSError:
            pass

    if not candidates:
        return []

    # Sort by mtime descending (stat each file)
    def _get_mtime(candidate: tuple[str, str]) -> float:
        try:
            return os.path.getmtime(candidate[1])
        except OSError:
            return 0.0

    candidates.sort(key=_get_mtime, reverse=True)

    # Apply offset
    candidates = candidates[offset:]

    # Read each file (lite) and parse metadata
    sessions: list[SessionInfo] = []
    seen: set[str] = set()
    for session_id, file_path in candidates:
        if len(sessions) >= limit:
            break
        lite = _read_file_lite(file_path)
        if lite is None:
            continue
        info = _parse_session_info(session_id, lite, cwd)
        if info is None or info.session_id in seen:
            continue
        seen.add(info.session_id)
        sessions.append(info)

    return sessions


def _scan_project_dir(project_dir: str) -> list[tuple[str, str]]:
    """List valid session .jsonl files in a project directory.

    Returns list of (session_id, file_path) tuples.
    """
    if not os.path.isdir(project_dir):
        return []
    results: list[tuple[str, str]] = []
    try:
        for filename in os.listdir(project_dir):
            if not filename.endswith(".jsonl"):
                continue
            session_id = _validate_uuid(filename[:-6])  # strip .jsonl
            if session_id:
                results.append((session_id, os.path.join(project_dir, filename)))
    except OSError:
        pass
    return results


async def get_session_info(session_id: str, cwd: str) -> SessionInfo | None:
    """Get metadata for a single session by ID."""
    project_dir = os.path.join(get_projects_dir(), sanitize_path(cwd))
    file_path = os.path.join(project_dir, f"{session_id}.jsonl")
    lite = _read_file_lite(file_path)
    if lite is None:
        return None
    return _parse_session_info(session_id, lite, cwd)
