"""WebFetchTool - fetch web page content.

Reference: cc-haha src/tools/WebFetchTool/WebFetchTool.ts
"""

from __future__ import annotations

import re
from typing import Any

from general_agent.tools.tool import Tool, ToolResult


class WebFetchTool(Tool):
    name = "WebFetch"
    max_result_size_chars = 50_000

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "format": "uri", "description": "URL to fetch"},
                "prompt": {"type": "string", "description": "What information to extract from the page"},
            },
            "required": ["url", "prompt"],
        }

    def is_read_only(self, args: dict[str, Any]) -> bool:
        return True

    def is_concurrency_safe(self, args: dict[str, Any]) -> bool:
        return True

    async def description(self, input: dict[str, Any] | None = None) -> str:
        return "Fetch and extract content from a web page"

    async def prompt(self) -> str:
        return """Fetch a web page and extract its content.

- HTTP URLs are automatically upgraded to HTTPS.
- Pages are converted to plain text (markdown-like format).
- Use `prompt` to describe what information you want to extract."""

    async def validate_input(
        self, args: dict[str, Any], context: Any = None
    ) -> dict | None:
        url = args.get("url", "").strip()
        if not url:
            return {"result": False, "message": "url is required"}
        if not url.startswith(("http://", "https://")):
            return {"result": False, "message": "url must start with http:// or https://"}
        return None

    async def call(self, args: dict[str, Any], context=None, **kw) -> ToolResult:
        url = args["url"]
        prompt = args.get("prompt", "")

        try:
            import httpx
            from html.parser import HTMLParser

            if url.startswith("http://"):
                url = url.replace("http://", "https://", 1)

            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "general-agent/0.1.0"},
                )

            if response.status_code != 200:
                return ToolResult(data={
                    "output": f"HTTP {response.status_code}: {response.reason_phrase}",
                    "status": response.status_code,
                })

            # Strip HTML tags, extract text
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type or "text/plain" in content_type:
                text = _html_to_text(response.text)
            else:
                text = response.text[:self.max_result_size_chars]

            if len(text) > self.max_result_size_chars:
                text = text[:self.max_result_size_chars] + "\n... (truncated)"

            # Add the prompt context
            output = f"## Content from {url}\n\n{text}\n\n---\n\nExtract prompt: {prompt}"
            return ToolResult(data={"output": output, "status": 200})

        except ImportError:
            # Try with urllib fallback
            import urllib.request
            try:
                with urllib.request.urlopen(url, timeout=15) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
                text = _html_to_text(text)
                if len(text) > self.max_result_size_chars:
                    text = text[:self.max_result_size_chars] + "\n... (truncated)"
                return ToolResult(data={"output": f"## Content from {url}\n\n{text}\n\n---\n\nPrompt: {prompt}", "status": 200})
            except Exception as e:
                return ToolResult(data={"output": f"Failed to fetch: {e}", "status": 0})
        except Exception as e:
            return ToolResult(data={"output": f"Failed to fetch: {e}", "status": 0})

    def map_tool_result_to_block(self, output: Any, tool_use_id: str) -> dict:
        text = output.get("output", str(output)) if isinstance(output, dict) else str(output)
        return {"type": "tool_result", "tool_use_id": tool_use_id, "content": text, "is_error": False}


def _html_to_text(html: str) -> str:
    """Basic HTML to text conversion - strip tags, preserve paragraph breaks."""
    # Remove script and style
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Replace block tags with newlines
    html = re.sub(r"</?(div|p|br|h[1-6]|li|tr|article|section)[^>]*>", "\n", html, flags=re.IGNORECASE)
    # Remove remaining tags
    html = re.sub(r"<[^>]+>", "", html)
    # Collapse whitespace
    lines = [line.strip() for line in html.split("\n")]
    return "\n".join(line for line in lines if line)
