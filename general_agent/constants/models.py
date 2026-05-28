"""Model constants for DeepSeek API.

DeepSeek endpoints:
  OpenAI-compatible:  https://api.deepseek.com
  Anthropic-compatible: https://api.deepseek.com/anthropic
"""

# Default model
DEFAULT_MODEL = "deepseek-v4-pro"

# Model aliases
MODEL_ALIASES: dict[str, str] = {
    "pro": "deepseek-v4-pro",
    "v4": "deepseek-v4-pro",
    "flash": "deepseek-v4-flash",
    "v4-flash": "deepseek-v4-flash",
    "chat": "deepseek-chat",
    "reasoner": "deepseek-reasoner",
}

# Friendly display names (matching cc-haha renderModelName pattern)
MODEL_DISPLAY_NAMES: dict[str, str] = {
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "deepseek-v4-flash": "DeepSeek V4 Flash",
    "deepseek-chat": "DeepSeek V3 (deprecated)",
    "deepseek-reasoner": "DeepSeek R1 (deprecated)",
}

# API endpoints
DEEPSEEK_OPENAI_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"

# Context window
MODEL_CONTEXT_WINDOW = 128_000

# Streaming watchdog
STREAM_IDLE_TIMEOUT_SECONDS = 90

# Retry
DEFAULT_MAX_RETRIES = 5
BASE_DELAY_MS = 500
