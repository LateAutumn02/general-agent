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

You have access to a persistent memory system in `.claude/memory/`.

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
    """Manages .claude/memory/ directory with YAML frontmatter + MEMORY.md index."""

    def __init__(self, root: str | None = None):
        self.root = root or os.path.join(os.getcwd(), ".claude", "memory")

    # --- Path helpers ---

    def resolve(self, name: str) -> str:
        safe = name.replace("/", "_").replace("\\", "_").replace(" ", "_")
        if not safe.endswith(".md"):
            safe += ".md"
        return os.path.join(self.root, safe)

    def ensure_dir(self) -> None:
        os.makedirs(self.root, exist_ok=True)

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

Review the conversation above and decide if there is anything worth remembering long-term.

**Existing memories:**
{existing_text}

**Instructions:**
1. Read existing memory files to understand what's already saved.
2. If you find something new worth remembering, write a memory file.
3. Each memory file must have YAML frontmatter (name, description, type).
4. Types: user, feedback, project, reference.
5. Do NOT save: code patterns, git history, debug notes, CLAUDE.md content, temporary task details.
6. If nothing new is worth saving, respond "Nothing new to remember."

Save new memories to `.claude/memory/<name>.md` using the Write tool.
Update existing memories with the Edit tool if they need refreshing."""

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
