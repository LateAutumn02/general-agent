"""Model and API constants — provider-agnostic.

The agent does not assume any specific provider.  All provider-specific
configuration comes from environment variables (set by the setup wizard):

  API_KEY    — API key
  BASE_URL   — API endpoint
  MODEL      — model name
  PROVIDER   — "openai" or "anthropic" format

Defaults below are fallbacks for when no configuration exists yet.
"""

# Default model (used if MODEL is not set)
DEFAULT_MODEL = ""

# Default API endpoints (fallbacks when BASE_URL is not set)
DEFAULT_OPENAI_BASE_URL = "https://api.deepseek.com"
DEFAULT_ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"

# Backward-compat alias (used by client.py)
DEEPSEEK_BASE_URL = DEFAULT_OPENAI_BASE_URL

# Context window default (most models support at least 200K)
MODEL_CONTEXT_WINDOW = 200_000

# Streaming watchdog
STREAM_IDLE_TIMEOUT_SECONDS = 90

# Retry
DEFAULT_MAX_RETRIES = 5
BASE_DELAY_MS = 500
