"""Tests for session path helpers and sanitization."""

import os
import pytest

from general_agent.session.store import (
    sanitize_path,
    get_project_dir,
    get_transcript_path,
    get_projects_dir,
    get_config_home,
)
from general_agent.bootstrap.state import reset_state_for_tests


class TestSanitizePath:
    """Test path sanitization for session storage."""

    def test_sanitize_windows_path(self):
        result = sanitize_path("C:\\Users\\Test\\project")
        assert "C:" not in result or ":" not in result
        assert "Users" in result or "users" in result.lower()
        assert "project" in result.lower()

    def test_sanitize_unix_path(self):
        result = sanitize_path("/home/user/my-project")
        assert "home" in result
        assert "user" in result
        assert "my-project" in result

    def test_sanitize_replaces_problematic_chars(self):
        result = sanitize_path("/path/with spaces/and*special?chars")
        assert " " not in result
        assert "*" not in result
        assert "?" not in result

    def test_sanitize_no_consecutive_underscores(self):
        result = sanitize_path("/a//b///c")
        assert "__" not in result

    def test_sanitize_root(self):
        result = sanitize_path("/")
        assert len(result) > 0
        # On Windows, realpath("/") resolves to the current drive root (e.g. "C")
        # On Unix, it stays as "/"
        assert "/" not in result  # no path separators in sanitized name
        assert len(result) > 0


class TestProjectPaths:
    """Test project directory and transcript path computation."""

    def test_config_home(self):
        path = get_config_home()
        assert ".general_agent" in path
        assert path.startswith(os.path.expanduser("~"))

    def test_projects_dir(self):
        path = get_projects_dir()
        assert path.endswith("projects")
        assert ".general_agent" in path

    def test_get_project_dir(self):
        path = get_project_dir("/home/user/test-project")
        assert path.startswith(get_projects_dir())
        assert "test-project" in path

    def test_get_transcript_path(self):
        path = get_transcript_path(
            "550e8400-e29b-41d4-a716-446655440000",
            "/home/user/test-project",
        )
        assert path.endswith("550e8400-e29b-41d4-a716-446655440000.jsonl")
        assert path.startswith(get_projects_dir())


class TestSessionStore:
    """Test the SessionStore class."""

    @pytest.fixture(autouse=True)
    def setup(self):
        reset_state_for_tests()
        from general_agent.session.store import reset_store_for_tests
        reset_store_for_tests()
        yield
        from general_agent.session.store import reset_store_for_tests
        reset_store_for_tests()

    def test_store_disabled_by_default(self):
        from general_agent.session.store import get_session_store
        store = get_session_store()
        # By default, store is not disabled
        assert not store._disabled  # noqa: SLF001

    def test_store_can_be_disabled(self):
        from general_agent.session.store import get_session_store
        store = get_session_store()
        store.disable()
        assert store.is_disabled()

    def test_save_user_message_returns_uuid(self):
        from general_agent.session.store import get_session_store
        store = get_session_store()
        uid = store.save_user_message(
            {"role": "user", "content": "Hello"},
            session_id="test-sid",
            cwd="/test/cwd",
        )
        assert uid
        assert len(uid) == 36  # UUID v4

    def test_save_user_message_skips_when_disabled(self):
        from general_agent.session.store import get_session_store
        store = get_session_store()
        store.disable()
        uid = store.save_user_message(
            {"role": "user", "content": "Hello"},
            session_id="test-sid",
            cwd="/test/cwd",
        )
        assert uid == ""

    def test_save_assistant_message_returns_uuid(self):
        from general_agent.session.store import get_session_store
        store = get_session_store()
        uid = store.save_assistant_message(
            {"role": "assistant", "content": "Hi there!"},
            session_id="test-sid",
            cwd="/test/cwd",
        )
        assert uid
        assert len(uid) == 36

    def test_insert_message_chain(self):
        from general_agent.session.store import get_session_store
        store = get_session_store()
        msgs = [
            {"role": "user", "content": "First"},
            {"role": "assistant", "content": "Response"},
        ]
        last_uuid = store.insert_message_chain(
            msgs, session_id="test-sid", cwd="/test/cwd"
        )
        assert last_uuid is not None

    def test_insert_message_chain_skips_when_disabled(self):
        from general_agent.session.store import get_session_store
        store = get_session_store()
        store.disable()
        last_uuid = store.insert_message_chain(
            [{"role": "user", "content": "Test"}],
            session_id="test-sid",
            cwd="/test/cwd",
        )
        assert last_uuid is None

    def test_flush_drains_queue(self, tmp_path):
        """Flush should write queued entries to disk."""
        from general_agent.session.store import get_session_store
        import asyncio
        store = get_session_store()
        # Set up a temp session file
        session_file = str(tmp_path / "test-session.jsonl")
        store._session_file = session_file  # noqa: SLF001
        store._disabled = False  # noqa: SLF001

        # Enqueue entries
        store.enqueue({"type": "user", "uuid": "u1", "text": "hello"})
        store.enqueue({"type": "assistant", "uuid": "u2", "text": "world"})

        # Flush
        asyncio.run(store.flush())

        # Check file was written
        with open(session_file, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2
        assert '"uuid": "u1"' in lines[0] or '"uuid":"u1"' in lines[0]
        assert '"uuid": "u2"' in lines[1] or '"uuid":"u2"' in lines[1]


class TestLoadTranscript:
    """Test transcript loading and chain reconstruction."""

    @pytest.fixture(autouse=True)
    def setup(self):
        reset_state_for_tests()
        from general_agent.session.store import reset_store_for_tests
        reset_store_for_tests()
        yield
        from general_agent.session.store import reset_store_for_tests
        reset_store_for_tests()

    def _write_jsonl(self, path, entries):
        import json
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    def test_load_empty_file(self, tmp_path):
        import asyncio
        from general_agent.session.store import get_session_store
        store = get_session_store()
        path = str(tmp_path / "empty.jsonl")
        result = asyncio.run(store.load_transcript(path))
        assert result["messages"] == []
        assert result["metadata"] == {}

    def test_load_nonexistent_file(self, tmp_path):
        from general_agent.session.store import get_session_store
        import asyncio
        store = get_session_store()
        path = str(tmp_path / "nonexistent.jsonl")
        result = asyncio.run(store.load_transcript(path))
        assert result["messages"] == []

    def test_load_simple_chain(self, tmp_path):
        from general_agent.session.store import get_session_store
        import asyncio
        store = get_session_store()

        entries = [
            {"type": "user", "uuid": "u1", "parentUuid": None,
             "sessionId": "s1", "timestamp": "2026-01-01T00:00:00+00:00",
             "message": {"role": "user", "content": "Hello"}},
            {"type": "assistant", "uuid": "u2", "parentUuid": "u1",
             "sessionId": "s1", "timestamp": "2026-01-01T00:00:01+00:00",
             "message": {"role": "assistant", "content": "Hi!"}},
        ]
        path = str(tmp_path / "simple.jsonl")
        self._write_jsonl(path, entries)

        result = asyncio.run(store.load_transcript(path))
        assert len(result["messages"]) == 2
        assert result["messages"][0]["type"] == "user"
        assert result["messages"][1]["type"] == "assistant"

    def test_load_extracts_metadata(self, tmp_path):
        from general_agent.session.store import get_session_store
        import asyncio
        store = get_session_store()

        entries = [
            {"type": "user", "uuid": "u1", "parentUuid": None,
             "sessionId": "s1", "timestamp": "2026-01-01T00:00:00+00:00",
             "message": {"role": "user", "content": "Test"}},
            {"type": "custom-title", "customTitle": "My Cool Session", "sessionId": "s1"},
            {"type": "tag", "tag": "important", "sessionId": "s1"},
        ]
        path = str(tmp_path / "with_meta.jsonl")
        self._write_jsonl(path, entries)

        result = asyncio.run(store.load_transcript(path))
        assert "custom-title" in result["metadata"]
        assert "tag" in result["metadata"]
