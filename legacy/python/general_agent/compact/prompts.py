"""Compact prompts - matching cc-haha prompt.ts pattern.

NO_TOOLS_PREAMBLE + 9-section template + NO_TOOLS_TRAILER.
"""

NO_TOOLS_PREAMBLE = """CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.
- Do NOT use Read, Bash, Grep, Glob, Edit, Write, or ANY other tool.
- Your entire response must be plain text: <analysis> then <summary>."""

NO_TOOLS_TRAILER = "REMINDER: Do NOT call any tools. Respond with plain text only."

COMPACT_PROMPT = """Summarize the conversation so far into these 9 sections:

<summary>
## 1. Primary Request and Intent
The user's explicit requests, goals, and what they want to achieve.

## 2. Key Technical Concepts
Technologies, frameworks, languages, and concepts discussed.

## 3. Files and Code Sections
Specific files examined, code snippets, and why they are important.

## 4. Errors and Fixes
Error messages encountered and how they were resolved.

## 5. Problem Solving
Issues solved and ongoing problems being worked on.

## 6. All User Messages
Every non-tool-result message from the user, verbatim if possible.

## 7. Pending Tasks
Tasks explicitly asked to complete but not yet done.

## 8. Current Work
Precisely what was being worked on when the summary was requested.
Include file paths and code context.

## 9. Optional Next Step
A directly relevant next step, with verbatim quotes from the user.
</summary>"""


def get_compact_prompt(custom_instructions: str = "") -> str:
    """Build the full compact prompt."""
    parts = [NO_TOOLS_PREAMBLE, COMPACT_PROMPT]
    if custom_instructions:
        parts.append(f"Additional Instructions:\n{custom_instructions}")
    parts.append(NO_TOOLS_TRAILER)
    return "\n\n".join(parts)


def format_compact_summary(text: str) -> str:
    """Strip <analysis> and extract <summary> from model output."""
    import re
    # Remove <analysis> section
    text = re.sub(r"<analysis>.*?</analysis>", "", text, flags=re.DOTALL)
    # Extract <summary> content
    match = re.search(r"<summary>(.*?)</summary>", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()
