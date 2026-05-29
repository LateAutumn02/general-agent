"""Session transcript - saves full conversation to disk.

Matching cc-haha sessionTranscript pattern.
Each message is saved as a JSON line in the session transcript file.
Stored at ~/.general_agent/transcripts/<session-id>.jsonl
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone


def get_transcript_path() -> str:
    """Get path for the current session transcript."""
    from general_agent.bootstrap.state import get_session_id
    sid = get_session_id()
    transcript_dir = os.path.join(os.path.expanduser("~"), ".general_agent", "transcripts")
    os.makedirs(transcript_dir, exist_ok=True)
    return os.path.join(transcript_dir, f"{sid}.jsonl")


def save_transcript(messages: list[dict]) -> None:
    """Append messages to the session transcript (JSONL format).

    Called after each conversation turn to preserve full history on disk.
    The full transcript is always available even after compact truncates
    the in-memory conversation.
    """
    try:
        path = get_transcript_path()
        timestamp = datetime.now(timezone.utc).isoformat()
        with open(path, "a", encoding="utf-8") as f:
            for msg in messages:
                entry = {"timestamp": timestamp, **msg}
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Transcript saving is best-effort, never blocks


def load_transcript() -> list[dict]:
    """Load the current session transcript from disk."""
    try:
        path = get_transcript_path()
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except Exception:
        return []
