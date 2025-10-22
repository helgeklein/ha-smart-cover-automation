"""Settings registry and resolution for smart_cover_automation.

This module defines a typo-safe enum of setting keys, a registry of specs with
defaults and coercion, and helpers to resolve effective settings from a
ConfigEntry (options → defaults).
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import time
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Callable, Generic, Mapping, TypeVar

from custom_components.smart_cover_automation.const import HA_OPTIONS

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class _ConfSpec(Generic[T]):
    """Metadata for a configuration setting.

    Attributes:
    - default: The default value for the setting.
    - converter: A callable that converts a raw value to the desired type T.
    """

    default: T
    converter: Callable[[Any], T]

    def __post_init__(self) -> None:
        # Disallow None default values to ensure ResolvedConfig fields are always concrete.
        if self.default is None:
            raise ValueError("_ConfSpec.default must not be None")


class ConfKeys(StrEnum):
    """Configuration keys for the integration's settings.

    Each key corresponds to a setting that can be configured via options.
    """

    AUTOMATION_DISABLED_TIME_RANGE = "automation_disabled_time_range"  # Disable the automation in a time range.
    AUTOMATION_DISABLED_TIME_RANGE_START = "automation_disabled_time_range_start"  # Start time for disabling the automation.
    AUTOMATION_DISABLED_TIME_RANGE_END = "automation_disabled_time_range_end"  # End time for disabling the automation.
    COVERS = "covers"  # Tuple of cover entity_ids to control.
    COVERS_MAX_CLOSURE = "covers_max_closure"  # Maximum closure position (0 = fully closed, 100 = fully open)
    COVERS_MIN_CLOSURE = "covers_min_closure"  # Minimum closure position (0 = fully closed, 100 = fully open)
    COVERS_MIN_POSITION_DELTA = "covers_min_position_delta"  # Ignore smaller position changes (%).
    ENABLED = "enabled"  # Global on/off for all automation.
    MANUAL_OVERRIDE_DURATION = "manual_override_duration"  # Duration (seconds) to skip a cover's automation after manual cover move.
    NIGHT_PRIVACY = "night_privacy"  # Night privacy: disable cover open automation at night.
    SIMULATION_MODE = "simulation_mode"  # Simulation mode: if enabled, no actual cover commands are sent.
    SUN_AZIMUTH_TOLERANCE = "sun_azimuth_tolerance"  # Max angle difference (°) to consider sun hitting.
    SUN_ELEVATION_THRESHOLD = "sun_elevation_threshold"  # Min sun elevation to act (degrees).
    TEMP_THRESHOLD = "temp_threshold"  # Temperature threshold at which heat protection activates (°C).
    VERBOSE_LOGGING = "verbose_logging"  # Enable DEBUG logs for this entry.
    WEATHER_ENTITY_ID = "weather_entity_id"  # Weather entity_id.
    WEATHER_HOT_CUTOVER_TIME = "weather_hot_cutover_time"  # Time of day to switch to next day's forecast for hot weather detection.


class _Converters:
    """Coercion helpers used by _ConfSpec."""

    @staticmethod
    def to_bool(v: Any) -> bool:
        """Convert various boolean representations to bool.

        Handles:
        - Native bool values: True, False
        - Integer values: 0 (False), non-zero (True)
        - String values: 'true', 'false', 'yes', 'no', 'on', 'off', '1', '0' (case-insensitive)
        - Other values: Python's default truthiness
        """
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            # Handle common string representations of boolean values
            normalized = v.lower().strip()
            if normalized in ("true", "yes", "on", "1"):
                return True
            if normalized in ("false", "no", "off", "0"):
                return False
            # For any other string values, use default truthiness (non-empty = True)
        return bool(v)

    @staticmethod
    def to_int(v: Any) -> int:
        return int(v)

    @staticmethod
    def to_float(v: Any) -> float:
        return float(v)

    @staticmethod
    def to_str(v: Any) -> str:
        return str(v)

    @staticmethod
    def to_covers_tuple(v: Any) -> tuple[str, ...]:
        if not v:
            return ()
        if isinstance(v, tuple):
            # Convert each element to str defensively
            return tuple(str(x) for x in v)
        if isinstance(v, list):
            return tuple(str(x) for x in v)
        # Fallback: mirror prior behavior (tuple(v)), which turns a string into chars
        try:
            return tuple(v)
        except Exception:
            return ()

    @staticmethod
    def to_duration_seconds(v: int | dict[str, Any]) -> int:
        """Convert HA duration format to total seconds (int).

        Accepts:
        - int: treated as seconds directly
        - dict: HA duration format like {"hours": 1, "minutes": 30, "seconds": 0}

        Returns total seconds as integer.
        """
        if isinstance(v, int):
            return max(0, v)

        if isinstance(v, dict):
            # HA duration format: {"days": 0, "hours": 1, "minutes": 30, "seconds": 0}
            days = v.get("days", 0)
            hours = v.get("hours", 0)
            minutes = v.get("minutes", 0)
            seconds = v.get("seconds", 0)

            total_seconds = (days * 24 * 60 * 60) + (hours * 60 * 60) + (minutes * 60) + seconds
            return max(0, int(total_seconds))

    @staticmethod
    def to_time(v: Any) -> time:
        """Convert various time representations to datetime.time.

        Accepts:
        - time: returned as-is
        - str: parsed as HH:MM:SS or HH:MM format

        Returns datetime.time object.
        """
        if isinstance(v, time):
            return v

        if isinstance(v, str):
            # Parse string like "16:00:00" or "16:00"
            parts = v.strip().split(":")
            if len(parts) == 2:
                # HH:MM format
                return time(hour=int(parts[0]), minute=int(parts[1]))
            elif len(parts) == 3:
                # HH:MM:SS format
                return time(hour=int(parts[0]), minute=int(parts[1]), second=int(parts[2]))

        raise ValueError(f"Cannot convert {v!r} to time")


# Type-only aliases so annotations can refer without exporting helpers.
if TYPE_CHECKING:  # pragma: no cover - type checking only
    Converters = _Converters
    ConfSpec = _ConfSpec


# Central registry of settings with defaults and coercion (type conversion).
# This is the single source of truth for all settings keys and their types.
CONF_SPECS: dict[ConfKeys, _ConfSpec[Any]] = {
    ConfKeys.AUTOMATION_DISABLED_TIME_RANGE: _ConfSpec(default=False, converter=_Converters.to_bool),
    ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_START: _ConfSpec(default=time(22, 0, 0), converter=_Converters.to_time),
    ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END: _ConfSpec(default=time(6, 0, 0), converter=_Converters.to_time),
    ConfKeys.COVERS: _ConfSpec(default=(), converter=_Converters.to_covers_tuple),
    ConfKeys.COVERS_MAX_CLOSURE: _ConfSpec(default=0, converter=_Converters.to_int),
    ConfKeys.COVERS_MIN_CLOSURE: _ConfSpec(default=100, converter=_Converters.to_int),
    ConfKeys.COVERS_MIN_POSITION_DELTA: _ConfSpec(default=5, converter=_Converters.to_int),
    ConfKeys.ENABLED: _ConfSpec(default=True, converter=_Converters.to_bool),
    ConfKeys.MANUAL_OVERRIDE_DURATION: _ConfSpec(default=1800, converter=_Converters.to_duration_seconds),
    ConfKeys.NIGHT_PRIVACY: _ConfSpec(default=True, converter=_Converters.to_bool),
    ConfKeys.SIMULATION_MODE: _ConfSpec(default=False, converter=_Converters.to_bool),
    ConfKeys.SUN_AZIMUTH_TOLERANCE: _ConfSpec(default=90, converter=_Converters.to_int),
    ConfKeys.SUN_ELEVATION_THRESHOLD: _ConfSpec(default=20.0, converter=_Converters.to_float),
    ConfKeys.TEMP_THRESHOLD: _ConfSpec(default=23.0, converter=_Converters.to_float),
    ConfKeys.VERBOSE_LOGGING: _ConfSpec(default=False, converter=_Converters.to_bool),
    ConfKeys.WEATHER_ENTITY_ID: _ConfSpec(default="", converter=_Converters.to_str),
    ConfKeys.WEATHER_HOT_CUTOVER_TIME: _ConfSpec(default=time(16, 0, 0), converter=_Converters.to_time),
}

# Public API of this module (keep helper class internal)
__all__ = [
    "ConfKeys",
    "CONF_SPECS",
    "ResolvedConfig",
    "resolve",
    "resolve_entry",
]


# Simple, explicit settings structure resolved from options → defaults.
@dataclass(frozen=True, slots=True)
class ResolvedConfig:
    automation_disabled_time_range: bool
    automation_disabled_time_range_start: time
    automation_disabled_time_range_end: time
    covers: tuple[str, ...]
    covers_max_closure: int
    covers_min_closure: int
    covers_min_position_delta: int
    enabled: bool
    manual_override_duration: int
    night_privacy: bool
    simulation_mode: bool
    sun_azimuth_tolerance: int
    sun_elevation_threshold: float
    temp_threshold: float
    verbose_logging: bool
    weather_entity_id: str
    weather_hot_cutover_time: time

    def get(self, key: ConfKeys) -> Any:
        # Generic access: ConfKeys values match dataclass field names
        return getattr(self, key.value)

    def as_enum_dict(self) -> dict[ConfKeys, Any]:
        # Build dict without hard-coded names
        return {k: getattr(self, k.value) for k in ConfKeys}


def resolve(options: Mapping[str, Any] | None) -> ResolvedConfig:
    """Resolve settings from options → defaults using ConfKeys.

    Only shallow keys are considered. Performs light normalization (covers → tuple).
    """
    options = options or {}

    def _val(key: ConfKeys) -> Any:
        spec = CONF_SPECS[key]
        if key.value in options:
            raw = options[key.value]
        else:
            raw = spec.default
        try:
            return spec.converter(raw)
        except Exception:
            # Fallback safely to default if coercion fails
            return spec.converter(spec.default)

    # Build kwargs dynamically by iterating over ConfKeys, applying light coercion
    converted: dict[str, Any] = {k.value: _val(k) for k in ConfKeys}

    # Filter strictly to ResolvedConfig fields and fail clearly if anything is missing
    field_names = {f.name for f in fields(ResolvedConfig)}
    missing_for_dc = field_names - converted.keys()
    if missing_for_dc:
        raise RuntimeError(f"Missing values for ResolvedConfig fields: {missing_for_dc}")

    values: dict[str, Any] = {name: converted[name] for name in field_names}
    return ResolvedConfig(**values)


def resolve_entry(entry: Any) -> ResolvedConfig:
    """Resolve settings directly from a ConfigEntry-like object.

    All user settings are stored in options. Accepts any object with 'options'
    attribute (works with test mocks).
    """
    opts = getattr(entry, HA_OPTIONS, None) or {}
    return resolve(opts)
