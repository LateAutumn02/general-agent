"""DeepSeek API client factory.

Uses OpenAI SDK pointed at DeepSeek's endpoint.
"""

from __future__ import annotations

import logging
import os

from general_agent.constants.models import DEEPSEEK_BASE_URL

logger = logging.getLogger("general_agent.api")


def get_client(api_key: str | None = None, base_url: str | None = None) -> object:
    """Create a configured OpenAI client pointed at DeepSeek.

    Returns:
        openai.OpenAI instance configured for DeepSeek API.
    """
    from openai import OpenAI

    if api_key is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")

    if base_url is None:
        base_url = os.environ.get("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL)

    client = OpenAI(api_key=api_key, base_url=base_url)

    logger.debug("Created DeepSeek client: base_url=%s", base_url)
    return client


def get_async_client(api_key: str | None = None, base_url: str | None = None) -> object:
    """Create an async OpenAI client for streaming."""
    from openai import AsyncOpenAI

    if api_key is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")

    if base_url is None:
        base_url = os.environ.get("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL)

    return AsyncOpenAI(api_key=api_key, base_url=base_url)
