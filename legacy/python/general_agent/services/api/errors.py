"""Error handling and retry logic for DeepSeek API.

Uses OpenAI SDK error types.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import AsyncGenerator

from openai import (
    APIError,
    APIConnectionError,
    AuthenticationError,
    InternalServerError,
    RateLimitError,
)

logger = logging.getLogger("general_agent.api")

# Retry configuration
BASE_DELAY_MS = 500
MAX_RETRIES = 5
JITTER_FACTOR = 0.25


class ErrorCategory(str, Enum):
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    AUTH_FAILURE = "auth_failure"
    SERVER_ERROR = "server_error"
    CONNECTION_ERROR = "connection_error"
    UNKNOWN = "unknown"


@dataclass
class SystemAPIErrorMessage:
    category: ErrorCategory
    message: str
    attempt: int = 0
    will_retry: bool = True


def _classify_error(error: Exception) -> tuple[ErrorCategory, bool]:
    if isinstance(error, RateLimitError):
        return ErrorCategory.RATE_LIMITED, True
    if isinstance(error, InternalServerError):
        return ErrorCategory.SERVER_ERROR, True
    if isinstance(error, APIConnectionError):
        return ErrorCategory.CONNECTION_ERROR, True
    if isinstance(error, AuthenticationError):
        return ErrorCategory.AUTH_FAILURE, False
    if isinstance(error, APIError):
        status = getattr(error, "status_code", 0)
        if 500 <= status < 600:
            return ErrorCategory.SERVER_ERROR, True
        if status == 429:
            return ErrorCategory.RATE_LIMITED, True
    return ErrorCategory.UNKNOWN, False


def _compute_delay(attempt: int) -> float:
    import random
    delay = BASE_DELAY_MS * (2 ** (attempt - 1)) / 1000.0
    jitter = delay * JITTER_FACTOR * (random.random() * 2 - 1)
    return max(0, delay + jitter)


async def with_retry(
    make_client,
    operation,
    *,
    max_retries: int = MAX_RETRIES,
    signal: asyncio.Event | None = None,
) -> AsyncGenerator:
    """Retry wrapper. Yields SystemAPIErrorMessage on retries, delegates to operation."""
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 2):
        if signal and signal.is_set():
            logger.info("Retry loop aborted by signal")
            return

        try:
            client = make_client()
            async for message in operation(client):
                yield message
            return
        except Exception as e:
            last_error = e
            category, should_retry = _classify_error(e)

            if not should_retry or attempt > max_retries:
                logger.error("API error (terminal): %s", e)
                raise

            delay = _compute_delay(attempt)
            logger.warning(
                "API error (attempt %d/%d): %s - retrying in %.1fs",
                attempt, max_retries, category.value, delay,
            )
            yield SystemAPIErrorMessage(
                category=category,
                message=f"Retrying ({attempt}/{max_retries})",
                attempt=attempt,
            )
            await asyncio.sleep(delay)

    if last_error:
        raise last_error
