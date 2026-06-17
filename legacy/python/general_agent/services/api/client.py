"""API client factory — reads config from environment variables.

Env vars (set by setup wizard):
  API_KEY   — API key (required)
  BASE_URL  — API endpoint (default: DeepSeek)
"""

from __future__ import annotations

import logging
import os

from general_agent.constants.models import DEEPSEEK_BASE_URL

logger = logging.getLogger("general_agent.api")


def _resolve_credentials(api_key: str | None, base_url: str | None) -> tuple[str, str]:
    """Resolve API key and base URL from explicit args or env vars."""
    if api_key is None:
        api_key = os.environ.get("API_KEY", "")
    if base_url is None:
        base_url = os.environ.get("BASE_URL", DEEPSEEK_BASE_URL)
    return api_key, base_url


def get_client(api_key: str | None = None, base_url: str | None = None) -> object:
    """Create a configured OpenAI client."""
    from openai import OpenAI

    api_key, base_url = _resolve_credentials(api_key, base_url)
    client = OpenAI(api_key=api_key, base_url=base_url)
    logger.debug("Created API client: base_url=%s", base_url)
    return client


def get_async_client(api_key: str | None = None, base_url: str | None = None) -> object:
    """Create an async OpenAI client for streaming."""
    from openai import AsyncOpenAI

    api_key, base_url = _resolve_credentials(api_key, base_url)
    return AsyncOpenAI(api_key=api_key, base_url=base_url)
