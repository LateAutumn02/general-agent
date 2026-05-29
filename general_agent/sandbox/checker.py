"""Sandbox platform detection and dependency check.

Matching cc-haha sandbox-adapter.ts pattern.
"""

import os
import shutil


def is_supported_platform() -> bool:
    """Check if the current platform supports sandboxing."""
    if os.name == "posix":
        if shutil.which("seatbelt") or shutil.which("bwrap"):
            return True  # macOS or Linux with bwrap
        return "linux" in os.uname().sysname.lower() if hasattr(os, "uname") else False
    return False  # Windows: no native sandbox support


def check_dependencies() -> dict:
    """Check if sandbox dependencies are available.

    Returns:
        dict with "available" (bool) and "errors" (list).
    """
    errors = []

    if not is_supported_platform():
        errors.append("Platform not supported - requires macOS (Seatbelt) or Linux (bwrap)")

    return {"available": len(errors) == 0, "errors": errors}


def is_sandbox_available() -> bool:
    """Quick check: can we use sandboxing right now?"""
    if os.name == "nt":
        return True  # Windows: pseudo-sandbox via path checking
    return is_supported_platform() and check_dependencies()["available"]


def get_sandbox_mode() -> str:
    """Describe the current sandbox implementation."""
    if os.name == "nt":
        return "path-based (Windows)"
    if shutil.which("seatbelt"):
        return "seatbelt (macOS)"
    if shutil.which("bwrap"):
        return "bwrap (Linux)"
    return "unavailable"
