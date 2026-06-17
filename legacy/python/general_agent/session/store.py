"""Session transcript store — JSONL persistence with buffered writes.

Matching cc-haha sessionStorage.ts Project class pattern.
Each message is appended as one JSON line. Uses parentUuid chain for
conversation reconstruction on resume.

Reference: cc-haha src/utils/sessionStorage.ts
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid as uuid_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("general_agent.session")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FLUSH_INTERVAL_S = 0.1          # 100ms batching window
LITE_READ_BUF_SIZE = 65536      # 64KB head/tail reads for metadata extraction
MAX_TRANSCRIPT_READ_BYTES = 50 * 1024 * 1024  # 50MB safety cap
MAX_SANITIZED_LENGTH = 150
VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# Path helpers (portable — no internal deps)
# ---------------------------------------------------------------------------

def get_config_home() -> str:
    """Return ~/.glagent directory."""
    return os.path.join(os.path.expanduser("~"), ".glagent")


def get_projects_dir() -> str:
    """Return ~/.glagent/projects directory."""
    return os.path.join(get_config_home(), "projects")


def sanitize_path(path: str) -> str:
    """Sanitize an absolute path into a safe directory name.

    Replaces problematic characters with '_' and truncates to MAX_SANITIZED_LENGTH.
    On conflict (long paths), appends a short hash suffix.

    Reference: cc-haha sessionStoragePortable.ts sanitizePath()
    """
    # Normalize — use realpath for existing paths, abspath for non-existent
    if os.path.exists(path):
        abs_path = os.path.realpath(path)
    else:
        abs_path = os.path.abspath(path)
    # On Windows, strip the drive letter colon
    sanitized = abs_path.replace(":", "_").replace("\\", "_").replace("/", "_")
    # Remove any other problematic chars
    result = ""
    for ch in sanitized:
        if ch.isalnum() or ch in "._-":
            result += ch
        else:
            result += "_"
    # Collapse consecutive underscores
    while "__" in result:
        result = result.replace("__", "_")
    # Strip leading/trailing underscores
    result = result.strip("_")
    if len(result) > MAX_SANITIZED_LENGTH:
        import hashlib
        h = hashlib.sha1(result.encode()).hexdigest()[:8]
        result = result[:MAX_SANITIZED_LENGTH - 9] + "-" + h
    return result or "root"


def get_project_dir(cwd: str) -> str:
    """Return project directory for a given working directory."""
    return os.path.join(get_projects_dir(), sanitize_path(cwd))


def get_transcript_path(session_id: str, cwd: str) -> str:
    """Return the full path for a session transcript JSONL file."""
    return os.path.join(get_project_dir(cwd), f"{session_id}.jsonl")


# ---------------------------------------------------------------------------
# Session store singleton
# ---------------------------------------------------------------------------

class SessionStore:
    """Manages session transcript persistence for the current session.

    Per-session singleton — call get_session_store() to access.
    Buffers writes and flushes asynchronously every 100ms.

    Reference: cc-haha sessionStorage.ts Project class
    """

    def __init__(self) -> None:
        self._session_file: str | None = None
        self._write_queue: list[dict[str, Any]] = []
        self._flush_task: asyncio.Task | None = None
        self._flush_lock = asyncio.Lock()
        self._session_metadata: dict[str, Any] = {}  # cached custom-title, tag, etc.
        self._message_uuids: set[str] = set()  # dedup set for current session
        self._disabled = False

    # ---- setup ----

    def disable(self) -> None:
        """Disable persistence (e.g. --no-session-persistence flag)."""
        self._disabled = True

    def is_disabled(self) -> bool:
        if self._disabled:
            return True
        # Also check bootstrap state flag
        try:
            from general_agent.bootstrap.state import is_session_persistence_disabled
            if is_session_persistence_disabled():
                return True
        except ImportError:
            pass
        return False

    def ensure_session_file(self, session_id: str, cwd: str) -> str:
        """Lazily compute and cache the session file path."""
        if self._session_file is None:
            self._session_file = get_transcript_path(session_id, cwd)
        return self._session_file

    # ---- metadata cache ----

    def set_metadata(self, key: str, value: Any) -> None:
        self._session_metadata[key] = value

    def get_metadata(self, key: str) -> Any:
        return self._session_metadata.get(key)

    def re_append_metadata(self) -> None:
        """Re-append session metadata entries to file tail.

        Ensures custom-title, tag, last-prompt stay in the last 64KB
        window for fast discovery reads. Called on session exit.

        Reference: cc-haha Project.reAppendSessionMetadata()
        """
        if not self._session_file:
            return
        entries: list[dict[str, Any]] = []
        session_id = self._session_metadata.get("session_id", "")
        if self._session_metadata.get("last_prompt"):
            entries.append({
                "type": "last-prompt",
                "lastPrompt": self._session_metadata["last_prompt"],
                "sessionId": session_id,
            })
        if self._session_metadata.get("custom_title"):
            entries.append({
                "type": "custom-title",
                "customTitle": self._session_metadata["custom_title"],
                "sessionId": session_id,
            })
        if self._session_metadata.get("tag"):
            entries.append({
                "type": "tag",
                "tag": self._session_metadata["tag"],
                "sessionId": session_id,
            })
        for entry in entries:
            self._append_to_file(self._session_file, entry)

    # ---- write path ----

    def enqueue(self, entry: dict[str, Any]) -> None:
        """Enqueue an entry and write immediately.

        Each entry is written to disk synchronously on enqueue —
        no buffering. The CLI agent processes one turn at a time,
        so batching offers no meaningful throughput gain.
        """
        if self.is_disabled():
            return
        self._track_uuid(entry)
        self._write_immediate(entry)

    def _write_immediate(self, entry: dict[str, Any]) -> None:
        """Write a single entry to disk immediately."""
        if self._session_file is None or self.is_disabled():
            return
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        self._append_to_file(self._session_file, line)

    async def flush(self) -> None:
        """No-op: writes are immediate. Kept for API compatibility."""

    def _append_to_file(self, file_path: str, data: str | dict[str, Any]) -> None:
        """Append data to a file. Creates directories if needed.

        Handles both string data (batch flush) and single dict entries
        (metadata re-append).
        """
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            if isinstance(data, dict):
                data = json.dumps(data, ensure_ascii=False) + "\n"
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(data)
        except Exception as e:
            logger.warning("Session write failed: %s", e)

    def _track_uuid(self, entry: dict[str, Any]) -> None:
        """Record UUID to in-memory set for dedup."""
        uid = entry.get("uuid")
        if uid:
            self._message_uuids.add(uid)

    def has_uuid(self, uid: str) -> bool:
        return uid in self._message_uuids

    # ---- main API: insert_message_chain ----

    def insert_message_chain(
        self,
        messages: list[dict[str, Any]],
        session_id: str,
        cwd: str,
        *,
        git_branch: str = "",
        starting_parent_uuid: str | None = None,
    ) -> str | None:
        """Persist a chain of messages to the session transcript.

        Each message gets stamped with session metadata (uuid, parentUuid,
        sessionId, timestamp, cwd, version, gitBranch).

        Returns the UUID of the last chain-participant message, or starting_parent_uuid.

        Reference: cc-haha Project.insertMessageChain()
        """
        if self.is_disabled():
            return starting_parent_uuid

        self.ensure_session_file(session_id, cwd)
        parent_uuid = starting_parent_uuid
        last_uuid = parent_uuid

        for msg in messages:
            if not self._is_chain_participant(msg):
                continue

            msg_uuid = str(uuid_lib.uuid4())
            msg.setdefault("uuid", msg_uuid)
            if "uuid" not in msg:
                msg["uuid"] = msg_uuid
            else:
                msg_uuid = msg["uuid"]

            entry = {
                "uuid": msg_uuid,
                "parentUuid": parent_uuid,
                "sessionId": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cwd": cwd,
                "version": VERSION,
                "gitBranch": git_branch,
                **msg,
            }
            self.enqueue(entry)
            parent_uuid = msg_uuid
            last_uuid = msg_uuid

        return last_uuid

    @staticmethod
    def _is_chain_participant(msg: dict[str, Any]) -> bool:
        """Filter out non-chain types (progress, etc.)."""
        msg_type = msg.get("type", "")
        return msg_type not in ("progress", "hook_progress")

    # ---- read path ----

    async def load_transcript(
        self,
        file_path: str,
    ) -> dict[str, Any]:
        """Load a transcript JSONL file and rebuild the conversation chain.

        Returns a dict with:
          - messages: list[dict] — reconstructed conversation in time order
          - metadata: dict — extracted session metadata

        Reference: cc-haha loadTranscriptFile() + buildConversationChain()
        """
        if not os.path.exists(file_path):
            return {"messages": [], "metadata": {}}

        # Read entries
        entries: list[dict[str, Any]] = []
        try:
            file_size = os.path.getsize(file_path)
            if file_size > MAX_TRANSCRIPT_READ_BYTES:
                logger.warning(
                    "Transcript too large (%d bytes), loading head+tail only",
                    file_size,
                )
            with open(file_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error("Failed to load transcript: %s", e)
            return {"messages": [], "metadata": {}}

        if not entries:
            return {"messages": [], "metadata": {}}

        # Build uuid -> entry map
        by_uuid: dict[str, dict[str, Any]] = {}
        transcript_entries: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}

        for entry in entries:
            entry_type = entry.get("type", "")
            if entry_type in ("custom-title", "tag", "agent-name", "last-prompt",
                              "mode", "worktree-state", "pr-link", "ai-title"):
                # Metadata entry — collect the latest value per type
                metadata[entry_type] = entry
                continue
            if entry_type in ("user", "assistant", "attachment", "system"):
                uid = entry.get("uuid")
                if uid:
                    by_uuid[uid] = entry
                transcript_entries.append(entry)

        # Find leaf: message with no child
        child_uuids: set[str] = set()
        for entry in transcript_entries:
            puid = entry.get("parentUuid")
            if puid:
                child_uuids.add(puid)
        leaf_candidates = [e for e in transcript_entries if e.get("uuid") not in child_uuids]

        if not leaf_candidates:
            # Fallback: use the last transcript entry as leaf
            leaf = transcript_entries[-1] if transcript_entries else None
        else:
            # Pick the latest (by timestamp)
            def _ts(entry: dict[str, Any]) -> float:
                try:
                    return datetime.fromisoformat(entry.get("timestamp", "")).timestamp()
                except (ValueError, OSError):
                    return 0.0
            leaf = max(leaf_candidates, key=_ts)

        if not leaf:
            return {"messages": [], "metadata": metadata}

        # Walk parentUuid chain from leaf to root, then reverse
        chain: list[dict[str, Any]] = []
        seen: set[str] = set()
        current: dict[str, Any] | None = leaf
        while current:
            uid = current.get("uuid")
            if not uid or uid in seen:
                break
            seen.add(uid)
            chain.append(current)
            puid = current.get("parentUuid")
            current = by_uuid.get(puid) if puid else None

        chain.reverse()

        # Fallback: if the parentUuid chain captured fewer than half the
        # transcript entries (e.g. old files with all-null parentUuids), just
        # use timestamp ordering for all entries.
        if len(chain) < len(transcript_entries) / 2:
            transcript_entries.sort(key=_ts)
            chain = transcript_entries
        else:
            # Recover orphaned parallel tool_results (cc-haha recoverOrphanedParallelToolResults)
            chain = self._recover_parallel_tool_results(by_uuid, chain, seen)

        return {"messages": chain, "metadata": metadata}

    @staticmethod
    def _recover_parallel_tool_results(
        by_uuid: dict[str, dict[str, Any]],
        chain: list[dict[str, Any]],
        seen: set[str],
    ) -> list[dict[str, Any]]:
        """Recover sibling tool_results orphaned by single-parent walk.

        When parallel tool_use blocks are emitted, each tool_use is a separate
        assistant message with the same message.id. The parentUuid walk only
        follows one branch. This pass recovers orphaned siblings.

        Reference: cc-haha recoverOrphanedParallelToolResults()
        """
        # Group assistant messages by message.id
        msg_id_group: dict[str, list[dict[str, Any]]] = {}
        for entry in by_uuid.values():
            if entry.get("type") != "assistant":
                continue
            msg_content = entry.get("message", {})
            msg_id = msg_content.get("id") if isinstance(msg_content, dict) else None
            if msg_id:
                msg_id_group.setdefault(msg_id, []).append(entry)

        # For each group that touches the chain, collect orphaned members
        chain_set = {m.get("uuid") for m in chain}
        inserts: dict[str, list[dict[str, Any]]] = {}

        for entries in msg_id_group.values():
            chain_members = [e for e in entries if e.get("uuid") in chain_set]
            if not chain_members:
                continue
            anchor = max(chain_members, key=lambda e: chain.index(e) if e in chain_set else -1)
            orphaned = [e for e in entries if e.get("uuid") not in seen]
            if orphaned:
                orphaned.sort(key=lambda e: e.get("timestamp", ""))
                for o in orphaned:
                    seen.add(o.get("uuid", ""))
                inserts.setdefault(anchor.get("uuid"), []).extend(orphaned)

        if not inserts:
            return chain

        # Splice in recovered messages after their anchors
        result: list[dict[str, Any]] = []
        for msg in chain:
            result.append(msg)
            extra = inserts.get(msg.get("uuid"))
            if extra:
                result.extend(extra)
        return result

    # ---- session save helper (called from agent loop) ----

    def save_user_message(
        self,
        msg: dict[str, Any],
        session_id: str,
        cwd: str,
        *,
        git_branch: str = "",
        parent_uuid: str | None = None,
    ) -> str:
        """Save a single user message. Returns its UUID."""
        if self.is_disabled():
            return ""
        self.ensure_session_file(session_id, cwd)
        msg_uuid = str(uuid_lib.uuid4())
        entry = {
            "type": "user",
            "uuid": msg_uuid,
            "parentUuid": parent_uuid,
            "sessionId": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cwd": cwd,
            "version": VERSION,
            "gitBranch": git_branch,
            "message": msg,
        }
        self.enqueue(entry)
        # Cache last prompt for resume display
        content = msg.get("content", "")
        text = content if isinstance(content, str) else (
            "".join(b.get("text", "") for b in content if b.get("type") == "text")
            if isinstance(content, list) else ""
        )
        if text:
            flat = text.replace("\n", " ").strip()
            self._session_metadata["last_prompt"] = (
                flat[:200] + "…" if len(flat) > 200 else flat
            )
        return msg_uuid

    def save_assistant_message(
        self,
        msg: dict[str, Any],
        session_id: str,
        cwd: str,
        *,
        git_branch: str = "",
        parent_uuid: str | None = None,
    ) -> str:
        """Save a single assistant message. Returns its UUID."""
        if self.is_disabled():
            return ""
        self.ensure_session_file(session_id, cwd)
        msg_uuid = str(uuid_lib.uuid4())
        entry = {
            "type": "assistant",
            "uuid": msg_uuid,
            "parentUuid": parent_uuid,
            "sessionId": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cwd": cwd,
            "version": VERSION,
            "gitBranch": git_branch,
            "message": msg,
        }
        self.enqueue(entry)
        return msg_uuid


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Return the singleton SessionStore instance."""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


def reset_store_for_tests() -> None:
    """Reset singleton for test isolation."""
    global _store
    _store = SessionStore()
