"""Shared utility helpers for the Smart Cover Automation integration."""

from __future__ import annotations

from typing import Any

__all__ = ["to_float_or_none", "to_int_or_none"]


def to_float_or_none(raw: Any) -> float | None:
    """Coerce ints/floats/strings to float; return None on failure or other types.

    This is useful when accepting user-provided values from config/options or entity attributes
    that may be numbers or numeric strings. Non-coercible values yield None.
    """
    if isinstance(raw, (int, float, str)):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    return None


def to_int_or_none(raw: Any) -> int | None:
    """Coerce ints/floats/strings to int; return None on failure or other types.

    This is useful when accepting user-provided values from config/options or entity attributes
    that may be numbers or numeric strings. Non-coercible values yield None.

    Note: Float values are truncated to int (not rounded).
    """
    if isinstance(raw, (int, float, str)):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    return None
