"""Shared utility helpers for the Smart Cover Automation integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.cover import CoverEntityFeature
from homeassistant.const import ATTR_SUPPORTED_FEATURES

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

__all__ = ["cover_supports_tilt", "to_float_or_none", "to_int_or_none"]


#
# cover_supports_tilt
#
def cover_supports_tilt(hass: HomeAssistant, cover_entity_id: str) -> bool | None:
    """Return whether a cover explicitly supports tilt.

    Returns ``True`` when the cover state is present and advertises
    ``SET_TILT_POSITION``, ``False`` when the state is present and does not
    support tilt, and ``None`` when tilt support cannot be determined from the
    current state.
    """

    states = getattr(hass, "states", None)
    if states is None:
        return None

    state = states.get(cover_entity_id)
    if state is None:
        return None

    features = state.attributes.get(ATTR_SUPPORTED_FEATURES)
    if features is None:
        return None

    try:
        return bool(int(features) & CoverEntityFeature.SET_TILT_POSITION)
    except (TypeError, ValueError):
        return None


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
