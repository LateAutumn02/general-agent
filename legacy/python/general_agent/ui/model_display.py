"""Model name formatting for compact UI display."""

MODEL_DISPLAY_MAX_LENGTH = 30


def format_model_for_display(model: str, max_length: int = MODEL_DISPLAY_MAX_LENGTH) -> str:
    """Shorten a model name for single-line UI bars."""
    if not model:
        return "---"
    if len(model) > max_length:
        return model[: max_length - 3] + "..."
    return model
