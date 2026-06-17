"""Memory store - matches cc-haha memdir pattern.

YAML frontmatter + .md files. MEMORY.md index. Four types.
Auto-extraction via post-run prompt (no fork agent in v1).

Reference: cc-haha src/memdir/memdir.ts, memoryTypes.ts
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any


# Frontmatter regex: --- ... --- at file start
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

MEMORY_TYPES = ("user", "feedback", "project", "reference")

# Prompt sections matching cc-haha memoryTypes.ts
BEHAVIOR_INSTRUCTIONS = """## Memory Instructions

You have access to a persistent memory system in `.glagent/memory/`.

### When to ACCESS memories
- At the start of a conversation or when the user mentions something that may have been discussed before
- Before making recommendations about user preferences, project decisions, or past approaches

### How to SAVE memories
Each memory is a `.md` file with YAML frontmatter:
```
---
name: <short title>
description: <one-line summary>
type: <user|feedback|project|reference>
---
<memory content>
```

### Memory types
- **user** — User's role, goals, preferences, knowledge (always private)
- **feedback** — Guidance and corrections about how to approach work
- **project** — Ongoing work context, initiatives, bugs, deadlines, decisions
- **reference** — Pointers to external systems (API URLs, doc links, etc.)

### What NOT to save
- Code patterns, syntax choices, framework usage details
- Git history or commit information
- Debugging notes or temporary fixes
- Content already in CLAUDE.md
- One-off task details

### When saving memories
- Avoid saving memories mid-task unless the user explicitly asks
- Save memories at the end of a conversation when the user says /memory save
- When asked to remember something, write a memory file immediately

### Trust but verify
- Memories are point-in-time observations and may be outdated
- Before acting on a memory, verify against current code state
"""


class MemoryStore:
    """Manages .glagent/memory/ directory with YAML frontmatter + MEMORY.md index."""

    def __init__(self, root: str | None = None):
        self.root = root or os.path.join(os.getcwd(), ".glagent", "memory")

    # --- Path helpers ---

    def resolve(self, name: str) -> str:
        safe = name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        if not safe.endswith(".md"):
            safe += ".md"
        return os.path.join(self.root, safe)

    def ensure_dir(self) -> None:
        os.makedirs(self.root, exist_ok=True)

    # --- Toggle persistence ---

    def is_enabled(self) -> bool:
        """Check if auto-memory is enabled. Default: False (opt-in)."""
        flag_path = os.path.join(self.root, ".memory_enabled")
        try:
            with open(flag_path, encoding="utf-8") as f:
                return f.read().strip() == "1"
        except FileNotFoundError:
            return False

    def set_enabled(self, val: bool) -> None:
        """Persist auto-memory on/off setting."""
        self.ensure_dir()
        flag_path = os.path.join(self.root, ".memory_enabled")
        with open(flag_path, "w", encoding="utf-8") as f:
            f.write("1" if val else "0")

    # --- CRUD ---

    def write(self, name: str, content: str, *,
              description: str = "", mem_type: str = "user") -> str:
        """Write a memory file with YAML frontmatter."""
        self.ensure_dir()
        if mem_type not in MEMORY_TYPES:
            mem_type = "user"

        frontmatter = f"---\nname: {name}\ndescription: {description}\ntype: {mem_type}\n---\n"
        path = self.resolve(name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(frontmatter + content)
        self._rebuild_index()
        return path

    def read(self, name: str) -> dict[str, Any] | None:
        """Read a memory file, returning {name, description, type, content}."""
        path = self.resolve(name)
        try:
            with open(path, encoding="utf-8") as f:
                raw = f.read()
        except FileNotFoundError:
            return None
        return self._parse(raw)

    def delete(self, name: str) -> bool:
        """Delete a memory file. Returns True if deleted."""
        path = self.resolve(name)
        try:
            os.unlink(path)
            self._rebuild_index()
            return True
        except FileNotFoundError:
            return False

    def list_all(self) -> list[dict[str, Any]]:
        """List all memories with frontmatter metadata."""
        if not os.path.exists(self.root):
            return []
        entries = []
        for fname in sorted(os.listdir(self.root)):
            if not fname.endswith(".md") or fname == "MEMORY.md":
                continue
            fpath = os.path.join(self.root, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    parsed = self._parse(f.read())
            except Exception:
                continue
            st = os.stat(fpath)
            parsed["filename"] = fname
            parsed["name"] = parsed.get("name", "") or fname.replace(".md", "")
            parsed["mtime"] = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
            parsed["age_days"] = (datetime.now(timezone.utc) -
                                  datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)).days
            entries.append(parsed)

        entries.sort(key=lambda e: e.get("age_days", 0) or 0, reverse=False)
        return entries

    def load_all(self) -> dict[str, dict]:
        """Load all memories (excluding MEMORY.md). Returns {name: {content, type, description}}."""
        if not os.path.exists(self.root):
            return {}
        result = {}
        for fname in sorted(os.listdir(self.root)):
            if not fname.endswith(".md") or fname == "MEMORY.md":
                continue
            try:
                with open(fpath := os.path.join(self.root, fname), encoding="utf-8") as f:
                    parsed = self._parse(f.read())
            except Exception:
                continue
            name = parsed.get("name", "") or fname.replace(".md", "")
            result[name] = {
                "content": parsed.get("content", ""),
                "type": parsed.get("type", "user") or "user",
                "description": parsed.get("description", ""),
                "path": fpath,
            }
        return result

    # --- MEMORY.md index ---

    def _rebuild_index(self) -> None:
        """Rebuild MEMORY.md index file to match current memories."""
        entries = self.list_all()
        lines = []
        for e in entries:
            desc = e.get("description", "") or ""
            name = e["name"]
            fname = e.get("filename", self.resolve(name))
            lines.append(f"- [{name}]({os.path.basename(fname)}) — {desc}")

        content = "\n".join(lines) + "\n"
        # Truncate to 200 lines / 25KB (cc-haha limits)
        line_list = content.split("\n")
        if len(line_list) > 200:
            line_list = line_list[:199] + [f"... ({len(line_list) - 200} more memories)"]
            content = "\n".join(line_list) + "\n"
        if len(content) > 25000:
            content = content[:24997] + "...\n"

        with open(os.path.join(self.root, "MEMORY.md"), "w", encoding="utf-8") as f:
            f.write(content)

    # --- Prompt formatting ---

    def format_for_prompt(self) -> str:
        """Format memories + behavioral instructions as system prompt section.

        Matching cc-haha's buildMemoryPrompt pattern:
        1. Behavioral instructions (how to save, when to access)
        2. MEMORY.md index content
        3. Individual memory file contents
        """
        parts = [BEHAVIOR_INSTRUCTIONS]

        memories = self.load_all()
        mem_list = self.list_all()

        if not memories:
            return BEHAVIOR_INSTRUCTIONS

        # MEMORY.md index
        idx_path = os.path.join(self.root, "MEMORY.md")
        if os.path.exists(idx_path):
            try:
                with open(idx_path, encoding="utf-8") as f:
                    idx = f.read()
                parts.append("\n## Memory Index\n")
                parts.append(idx)
            except Exception:
                pass

        # Individual memories with freshness warnings
        parts.append("\n## Full Memory Content\n")
        for entry in mem_list:
            name = entry["name"]
            mem = memories.get(name)
            if not mem:
                continue

            age = entry.get("age_days", 0)
            fresh = "today" if age == 0 else "yesterday" if age == 1 else f"{age} days ago"
            tag = f"[{mem.get('type', 'user')}] • {fresh}"

            if age > 1:
                parts.append(
                    f"<system-reminder>\n"
                    f"  This memory is {age} days old. Memories are point-in-time "
                    f"observations. Verify against current code before asserting as fact.\n"
                    f"</system-reminder>"
                )

            parts.append(f"### {name}  `{tag}`")
            content = mem.get("content", "")
            if len(content) > 2000:
                content = content[:1997] + "..."
            parts.append(content)
            parts.append("")

        return "\n".join(parts)

    # --- Format only relevant memories (per-query) ---

    def format_relevant(self, names: list[str]) -> str:
        """Format only selected memories + behavioral instructions + staleness warnings."""
        parts = [BEHAVIOR_INSTRUCTIONS]

        if not names:
            return BEHAVIOR_INSTRUCTIONS

        memories = self.load_all()
        mem_list = self.list_all()

        parts.append("\n## Relevant Memories\n")
        for entry in mem_list:
            if entry["name"] not in names:
                continue
            mem = memories.get(entry["name"])
            if not mem:
                continue

            age = entry.get("age_days", 0)
            fresh = "today" if age == 0 else "yesterday" if age == 1 else f"{age} days ago"
            tag = f"[{mem.get('type', 'user')}] • {fresh}"

            if age > 1:
                parts.append(
                    f"<system-reminder>\n"
                    f"  This memory is {age} days old. Verify against current code.\n"
                    f"</system-reminder>"
                )

            parts.append(f"### {entry['name']}  `{tag}`")
            content = mem.get("content", "")
            if len(content) > 2000:
                content = content[:1997] + "..."
            parts.append(content)
            parts.append("")

        return "\n".join(parts)

    # --- Auto-extraction prompt ---

    def build_extraction_prompt(self) -> str:
        """Prompt to ask the agent to review conversation and save memories.

        Injected after run_agent() completes. No fork agent needed.
        Matches cc-haha extractMemories prompt pattern.
        """
        memories = self.load_all()
        existing = []
        for name, info in memories.items():
            existing.append(f"  - [{info.get('type', 'user')}] {name}: {info.get('description', '')}")

        existing_text = "\n".join(existing) if existing else "  (no existing memories)"

        return f"""## Memory Review

The conversation above may contain information worth remembering. You MUST check.

Step 1: Read existing memory files first (they're in .glagent/memory/).
Step 2: Then decide if any NEW information should be saved.
Step 3: Use the Write tool to save new memories. Use the Edit tool to update existing ones.
Step 4: Write a 1-line summary of what you saved, or "Checked, memories are up to date."

Rules:
- Each memory file MUST have YAML frontmatter: name, description, type
- Types: user, feedback, project, reference
- Do NOT save: code patterns, git history, debug notes, CLAUDE.md content, temp details
- User names and preferences are type=user. Project decisions are type=project.

Existing memories for reference:
{existing_text}

Start by reading current memories, then decide what to add or update."""

    # --- Parsing ---

    @staticmethod
    def _parse(raw: str) -> dict[str, Any]:
        """Parse a memory file: extract frontmatter and body."""
        result: dict[str, Any] = {"name": "", "description": "", "type": "user", "content": ""}
        m = _FRONTMATTER_RE.match(raw)
        if m:
            body = raw[m.end():].strip()
            front_text = m.group(1)
            for line in front_text.split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    val = val.strip()
                    if key in ("name", "description", "type"):
                        result[key] = val
            result["content"] = body
        else:
            result["content"] = raw.strip()
        return result

    # --- On-demand retrieval ---

    async def find_relevant(self, query: str, limit: int = 5) -> list[str]:
        """Select up to N relevant memory files for a given query.

        Uses a lightweight API call to pick which memories are relevant.
        Matching cc-haha findRelevantMemories.ts pattern.
        """
        memories = self.load_all()
        if not memories:
            return []

        # Build manifest of all memories (matching cc-haha scanMemoryFiles)
        manifest_lines = []
        for name, info in memories.items():
            manifest_lines.append(
                f"  [{info.get('type', 'user')}] {name}: {info.get('description', '')}"
            )

        if len(manifest_lines) <= limit:
            return list(memories.keys())

        manifest = "\n".join(manifest_lines)
        memory_names = list(memories.keys())

        try:
            selected = await _select_relevant_memories(query, manifest, memory_names, limit)
            return [n for n in selected if n in memories]
        except Exception:
            # Fallback: return all (limit to N)
            return memory_names[:limit]

    # --- Session Memory ---

    def get_session_memory_path(self) -> str:
        """Path to the per-project session memory file."""
        from general_agent.bootstrap.state import get_session_id
        sid = get_session_id()[:8]
        return os.path.join(self.root, ".session", f"{sid}.md")

    def load_session_memory(self) -> str:
        """Load the current session's memory."""
        path = self.get_session_memory_path()
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return SESSION_MEMORY_TEMPLATE

    def save_session_memory(self, content: str) -> None:
        """Save session memory for the current session."""
        path = self.get_session_memory_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    # --- AutoDream (nightly consolidation) ---

    def should_dream(self, min_hours: int = 24, min_memories: int = 3) -> bool:
        """Check if memory consolidation should run.

        Returns True if memories are at least min_hours old and there are enough.
        """
        entries = self.list_all()
        if len(entries) < min_memories:
            return False

        lock_path = os.path.join(self.root, ".consolidate-lock")
        try:
            mtime = os.path.getmtime(lock_path)
            age_hours = (datetime.now(timezone.utc).timestamp() - mtime) / 3600
            return age_hours >= min_hours
        except FileNotFoundError:
            return True  # Never dreamed before

    def touch_dream_lock(self) -> None:
        """Mark consolidation as done."""
        lock_path = os.path.join(self.root, ".consolidate-lock")
        os.makedirs(self.root, exist_ok=True)
        with open(lock_path, "w") as f:
            f.write(f"dreamed at {datetime.now(timezone.utc).isoformat()}\n")

    def build_dream_prompt(self) -> str:
        """Prompt to ask the agent to consolidate memories.

        Matching cc-haha autoDream/consolidationPrompt.ts pattern.
        """
        entries = self.list_all()
        manifest = []
        for e in entries:
            manifest.append(
                f"  - [{e.get('type', 'user')}] {e['name']}: {e.get('description', '')}"
                f" ({e.get('age_days', 0)} days old)"
            )
        manifest_text = "\n".join(manifest) if manifest else "(none)"

        return f"""## Memory Consolidation (AutoDream)

Your memory files are getting stale. Review and consolidate them.

**Current memories:**
{manifest_text}

**Instructions:**
1. Read each memory file to understand what's saved
2. If any information is outdated or wrong, edit the file to correct it
3. If two memories overlap significantly, merge them into one
4. Delete memories that are no longer relevant
5. Convert relative dates to absolute dates
6. Keep the MEMORY.md index under 200 lines
7. Respond with a summary of what you changed, or 'Memories are up to date.'"""


# ---------------------------------------------------------------------------
# Session Memory template (matching cc-haha prompts.ts)
# ---------------------------------------------------------------------------

SESSION_MEMORY_TEMPLATE = """# Session Memory

## Current State
What am I working on?

## Task specification
What does the user want me to do?

## Files and Functions
Key files and their purpose in the current task.

## Workflow
Common commands and their execution order.

## Errors & Corrections
Errors encountered and how they were fixed.

## Learnings
What worked and what didn't.

## Key Results
Outputs the user asked for.

## Worklog
Step-by-step log of what was attempted and done.
"""


# ---------------------------------------------------------------------------
# Helper: select relevant memories via API
# ---------------------------------------------------------------------------

async def _select_relevant_memories(
    query: str, manifest: str, names: list[str], limit: int = 5
) -> list[str]:
    """Call the API to select which memories are relevant to the query.

    Uses a simple classification prompt. No fork agent needed.
    Matching cc-haha selectRelevantMemories flow.
    """
    import json

    from general_agent.services.api.messages import query_model_without_streaming

    prompt = f"""You are selecting which saved memories are relevant to a question.

User question: {query}

Available memories:
{manifest}

Return ONLY a JSON array of memory names that are relevant.
Example: ["user_prefs", "project_deadlines"]
Limit to {limit} or fewer. Be selective."""

    try:
        result = await query_model_without_streaming(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="",
            temperature=0.3,
            max_tokens=200,
        )
        text = ""
        content = result.get("content", "")
        if isinstance(content, list):
            for block in content:
                if block.get("type") == "text":
                    text += block.get("text", "")
        else:
            text = str(content)

        # Extract JSON array from response
        import re
        match = re.search(r"\[.*?\]", text, re.DOTALL)
        if match:
            selected = json.loads(match.group())
            return [n for n in selected if n in names][:limit]
    except Exception:
        pass

    return names[:limit]


# ---------------------------------------------------------------------------
# Team Memory (stub - to be implemented with multi-agent)
# ---------------------------------------------------------------------------

class TeamMemory:
    """Team-shared memory directory. Stub for multi-agent support.

    Reference: cc-haha src/memdir/teamMemPaths.ts
    """

    def __init__(self, root: str):
        self.root = os.path.join(root, "team")

    def ensure_dir(self) -> None:
        os.makedirs(self.root, exist_ok=True)

    # TODO: Implement team memory loading, validation, scope resolution
    # when multi-agent system is available.


