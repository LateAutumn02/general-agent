"""Sandbox settings and decision logic.

Matching cc-haha shouldUseSandbox.ts pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SandboxSettings:
    """Sandbox configuration."""
    enabled: bool = False
    allow_unsandboxed: bool = True  # Allow dangerouslyDisableSandbox parameter
    auto_allow_bash: bool = True    # Auto-allow sandboxed bash without permission prompt
    excluded_commands: list[str] = field(default_factory=list)
    fail_if_unavailable: bool = False


# Global settings instance
_settings = SandboxSettings()


def get_settings() -> SandboxSettings:
    return _settings


def set_settings(**kwargs) -> None:
    for k, v in kwargs.items():
        if hasattr(_settings, k):
            setattr(_settings, k, v)


def should_use_sandbox(command: str) -> bool:
    """Decide whether to sandbox a bash command.

    Matching cc-haha shouldUseSandbox flow:
    1. Sandbox disabled globally → False
    2. Command matches excluded pattern → False
    3. Otherwise → True
    """
    if not _settings.enabled:
        return False

    cmd = command.strip()
    if not cmd:
        return False

    for pattern in _settings.excluded_commands:
        if pattern in cmd:
            return False

    return True


def is_sandbox_enabled() -> bool:
    return _settings.enabled


def toggle_sandbox(enabled: bool) -> None:
    _settings.enabled = enabled
