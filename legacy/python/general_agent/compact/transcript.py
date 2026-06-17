"""Session transcript — bridges to the session persistence module.

Delegates to general_agent.session.store for actual persistence logic.
Kept as a thin wrapper for backward compatibility.

Reference: cc-haha src/services/sessionTranscript/sessionTranscript.ts
"""

from __future__ import annotations

import json
import os
from typing import Any


def get_transcript_path() -> str:
    """Get path for the current session transcript."""
    from general_agent.session.store import get_session_store, get_transcript_path as _gtp
    from general_agent.bootstrap.state import get_session_id, get_original_cwd

    store = get_session_store()
    if store._session_file:  # noqa: SLF001
        return store._session_file  # noqa: SLF001
    return _gtp(get_session_id(), get_original_cwd())


def save_transcript(messages: list[dict[str, Any]]) -> None:
    """Append messages to the session transcript via session store.

    Called after each assistant message in the agent loop.
    """
    try:
        from general_agent.session.store import get_session_store
        from general_agent.bootstrap.state import get_session_id, get_original_cwd

        store = get_session_store()
        session_id = get_session_id()
        cwd = get_original_cwd()

        for msg in messages:
            if msg.get("role") == "assistant":
                store.save_assistant_message(msg, session_id, cwd)
            elif msg.get("role") == "user":
                store.save_user_message(msg, session_id, cwd)
    except Exception:
        pass  # Transcript saving is best-effort, never blocks


def load_transcript() -> list[dict[str, Any]]:
    """Load the current session transcript from disk."""
    try:
        path = get_transcript_path()
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except Exception:
        return []
