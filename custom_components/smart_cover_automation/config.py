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

from custom_components.smart_cover_automation.const import (
    COVER_SFX_TILT_EXTERNAL_VALUE_DAY,
    COVER_SFX_TILT_EXTERNAL_VALUE_NIGHT,
    COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL,
    HA_OPTIONS,
    LEGACY_OPTION_KEY_TEMPERATURE_THRESHOLD,
    NUMBER_KEY_DAILY_MAX_TEMPERATURE_THRESHOLD,
    NUMBER_KEY_DAILY_MIN_TEMPERATURE_THRESHOLD,
    NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY,
    NUMBER_KEY_TILT_EXTERNAL_VALUE_NIGHT,
    SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL,
    SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL,
    TIME_KEY_EVENING_CLOSURE_EXTERNAL_TIME,
    TIME_KEY_MORNING_OPENING_EXTERNAL_TIME,
    EveningClosureMode,
    LockMode,
    MorningOpeningMode,
    ReopeningMode,
    TiltMode,
)

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class _ConfSpec(Generic[T]):
    """Metadata for a configuration setting.

    Attributes:
    - default: The default value for the setting.
    - converter: A callable that converts a raw value to the desired type T.
    - runtime_configurable: Whether this setting can be changed at runtime via an entity
                           (switch, number, select) without requiring a full integration reload.
                           Settings with corresponding control entities should be True.
    """

    default: T
    converter: Callable[[Any], T]
    runtime_configurable: bool = False

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
    EVENING_CLOSURE_ENABLED = "close_covers_after_sunset"  # Evening closure: enabled.
    EVENING_CLOSURE_MODE = "close_covers_after_sunset_mode"  # Evening closure: timing mode.
    EVENING_CLOSURE_TIME = "close_covers_after_sunset_delay"  # Evening closure: time value.
    EVENING_CLOSURE_COVER_LIST = "close_covers_after_sunset_cover_list"  # Evening closure: list of covers.
    EVENING_CLOSURE_MAX_CLOSURE = "close_covers_after_sunset_max_closure"  # Evening closure: cover position.
    EVENING_CLOSURE_IGNORE_MANUAL_OVERRIDE_DURATION = (
        "close_covers_after_sunset_ignore_manual_override_duration"  # Evening closure: ignore manual override duration.
    )
    EVENING_CLOSURE_KEEP_CLOSED = "close_covers_after_sunset_keep_closed"  # Evening closure: keep covers closed overnight.
    MORNING_OPENING_MODE = "morning_opening_mode"  # Morning opening: timing mode.
    MORNING_OPENING_TIME = "morning_opening_time"  # Morning opening: time value.
    AUTOMATIC_REOPENING_MODE = "automatic_reopening_mode"  # Automatic reopening behavior after automation-driven closures.
    COVERS = "covers"  # Tuple of cover entity_ids to control.
    COVERS_MAX_CLOSURE = "covers_max_closure"  # Maximum closure position (0 = fully closed, 100 = fully open)
    COVERS_MIN_CLOSURE = "covers_min_closure"  # Minimum closure position (0 = fully closed, 100 = fully open)
    COVERS_MIN_POSITION_DELTA = "covers_min_position_delta"  # Ignore smaller position changes (%).
    ENABLED = "enabled"  # Global on/off for all automation.
    LOCK_MODE = "lock_mode"  # Current lock mode for all covers.
    MANUAL_OVERRIDE_DURATION = "manual_override_duration"  # Duration (seconds) to skip a cover's automation after manual cover move.
    SIMULATION_MODE = "simulation_mode"  # If enabled, no actual cover commands are sent.
    DAILY_MAX_TEMPERATURE_THRESHOLD = (
        "daily_max_temperature_threshold"  # Daily high temperature threshold at which heat protection can activate (°C).
    )
    DAILY_MIN_TEMPERATURE_THRESHOLD = (
        "daily_min_temperature_threshold"  # Daily low temperature threshold at which heat protection can activate (°C).
    )
    SUN_AZIMUTH_TOLERANCE = "sun_azimuth_tolerance"  # Max angle difference (°) to consider sun hitting.
    SUN_ELEVATION_THRESHOLD = "sun_elevation_threshold"  # Min sun elevation to act (degrees).
    TILT_MIN_CHANGE_DELTA = "tilt_min_change_delta"  # Minimum tilt change (%) to actually send a service call.
    TILT_OPEN_TO_COVER_OPEN_DELAY = (
        "tilt_open_to_cover_open_delay"  # Delay stored in minutes between opening tilt and reopening the cover in day auto mode.
    )
    TILT_VERTICAL_POSITION = "tilt_vertical_position"  # HA tilt position that corresponds to vertical slats in Auto mode.
    TILT_HORIZONTAL_POSITION = "tilt_horizontal_position"  # HA tilt position that corresponds to horizontal slats in Auto mode.
    TILT_MODE_DAY = "tilt_mode_day"  # Global tilt mode during daytime.
    TILT_MODE_NIGHT = "tilt_mode_night"  # Global tilt mode at night / evening closure.
    TILT_SET_VALUE_DAY = "tilt_set_value_day"  # Fixed tilt angle (0-100) for day "set_value" mode.
    TILT_SET_VALUE_NIGHT = "tilt_set_value_night"  # Fixed tilt angle (0-100) for night "set_value" mode.
    TILT_SLAT_OVERLAP_RATIO = "tilt_slat_overlap_ratio"  # Slat spacing/width ratio (d/L) for Auto tilt calculation.
    VERBOSE_LOGGING = "verbose_logging"  # Enable DEBUG logs for this entry.
    WEATHER_ENTITY_ID = "weather_entity_id"  # Weather entity_id.
    WEATHER_HOT_CUTOVER_TIME = "weather_hot_cutover_time"  # Time of day to switch max-temperature checks to next day's forecast.


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
    ConfKeys.AUTOMATION_DISABLED_TIME_RANGE_END: _ConfSpec(default=time(8, 0, 0), converter=_Converters.to_time),
    ConfKeys.EVENING_CLOSURE_ENABLED: _ConfSpec(default=False, converter=_Converters.to_bool),
    ConfKeys.EVENING_CLOSURE_MODE: _ConfSpec(default=EveningClosureMode.AFTER_SUNSET, converter=EveningClosureMode),
    ConfKeys.EVENING_CLOSURE_TIME: _ConfSpec(default=time(0, 15, 0), converter=_Converters.to_time),
    ConfKeys.EVENING_CLOSURE_COVER_LIST: _ConfSpec(default=(), converter=_Converters.to_covers_tuple),
    ConfKeys.EVENING_CLOSURE_MAX_CLOSURE: _ConfSpec(default=0, converter=_Converters.to_int, runtime_configurable=True),
    ConfKeys.EVENING_CLOSURE_IGNORE_MANUAL_OVERRIDE_DURATION: _ConfSpec(default=True, converter=_Converters.to_bool),
    ConfKeys.EVENING_CLOSURE_KEEP_CLOSED: _ConfSpec(default=True, converter=_Converters.to_bool),
    ConfKeys.MORNING_OPENING_MODE: _ConfSpec(
        default=MorningOpeningMode.FIXED_TIME,
        converter=MorningOpeningMode,
    ),
    ConfKeys.MORNING_OPENING_TIME: _ConfSpec(default=time(8, 0, 0), converter=_Converters.to_time),
    ConfKeys.AUTOMATIC_REOPENING_MODE: _ConfSpec(
        default=ReopeningMode.PASSIVE,
        converter=ReopeningMode,
        runtime_configurable=True,
    ),
    ConfKeys.COVERS: _ConfSpec(default=(), converter=_Converters.to_covers_tuple),
    ConfKeys.COVERS_MAX_CLOSURE: _ConfSpec(default=0, converter=_Converters.to_int, runtime_configurable=True),
    ConfKeys.COVERS_MIN_CLOSURE: _ConfSpec(default=100, converter=_Converters.to_int, runtime_configurable=True),
    ConfKeys.COVERS_MIN_POSITION_DELTA: _ConfSpec(default=5, converter=_Converters.to_int),
    ConfKeys.ENABLED: _ConfSpec(default=True, converter=_Converters.to_bool, runtime_configurable=True),
    ConfKeys.LOCK_MODE: _ConfSpec(default=LockMode.UNLOCKED, converter=LockMode, runtime_configurable=True),
    ConfKeys.MANUAL_OVERRIDE_DURATION: _ConfSpec(default=1800, converter=_Converters.to_duration_seconds, runtime_configurable=True),
    ConfKeys.SIMULATION_MODE: _ConfSpec(default=False, converter=_Converters.to_bool, runtime_configurable=True),
    ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD: _ConfSpec(default=24.0, converter=_Converters.to_float, runtime_configurable=True),
    ConfKeys.DAILY_MIN_TEMPERATURE_THRESHOLD: _ConfSpec(default=13.0, converter=_Converters.to_float, runtime_configurable=True),
    ConfKeys.SUN_AZIMUTH_TOLERANCE: _ConfSpec(default=90, converter=_Converters.to_int, runtime_configurable=True),
    ConfKeys.SUN_ELEVATION_THRESHOLD: _ConfSpec(default=0.0, converter=_Converters.to_float, runtime_configurable=True),
    ConfKeys.TILT_MIN_CHANGE_DELTA: _ConfSpec(default=5, converter=_Converters.to_int),
    ConfKeys.TILT_OPEN_TO_COVER_OPEN_DELAY: _ConfSpec(default=0, converter=_Converters.to_int),
    ConfKeys.TILT_VERTICAL_POSITION: _ConfSpec(default=0, converter=_Converters.to_int),
    ConfKeys.TILT_HORIZONTAL_POSITION: _ConfSpec(default=100, converter=_Converters.to_int),
    ConfKeys.TILT_MODE_DAY: _ConfSpec(default=TiltMode.AUTO, converter=TiltMode),
    ConfKeys.TILT_MODE_NIGHT: _ConfSpec(default=TiltMode.CLOSED, converter=TiltMode),
    ConfKeys.TILT_SET_VALUE_DAY: _ConfSpec(default=50, converter=_Converters.to_int),
    ConfKeys.TILT_SET_VALUE_NIGHT: _ConfSpec(default=0, converter=_Converters.to_int),
    ConfKeys.TILT_SLAT_OVERLAP_RATIO: _ConfSpec(default=0.9, converter=_Converters.to_float),
    ConfKeys.VERBOSE_LOGGING: _ConfSpec(default=False, converter=_Converters.to_bool, runtime_configurable=True),
    ConfKeys.WEATHER_ENTITY_ID: _ConfSpec(default="", converter=_Converters.to_str),
    ConfKeys.WEATHER_HOT_CUTOVER_TIME: _ConfSpec(default=time(16, 0, 0), converter=_Converters.to_time),
}

# Public API of this module (keep helper class internal)
__all__ = [
    "ConfKeys",
    "CONF_SPECS",
    "ResolvedConfig",
    "get_runtime_configurable_keys",
    "is_runtime_configurable_key",
    "resolve",
    "resolve_entry",
]


#
# get_runtime_configurable_keys
#
def get_runtime_configurable_keys() -> set[str]:
    """Return the set of configuration keys that can be changed at runtime.

    These keys have corresponding entities (switches, numbers, selects) and
    changes to them only require a coordinator refresh, not a full reload.

    This includes both keys from CONF_SPECS marked as runtime_configurable
    and the weather sunny external control switch key, which lives outside
    the spec system due to its tri-state semantics (absent / True / False).

    Returns:
        Set of configuration key strings that are runtime configurable
    """

    keys = {key.value for key, spec in CONF_SPECS.items() if spec.runtime_configurable}
    # The external control switch is not part of CONF_SPECS (it uses tri-state
    # semantics: absent means "use forecast", True/False means override).
    # Include it here so toggling the switch triggers a coordinator refresh
    # rather than a full integration reload.
    keys.add(SWITCH_KEY_WEATHER_SUNNY_EXTERNAL_CONTROL)
    keys.add(SWITCH_KEY_WEATHER_HOT_EXTERNAL_CONTROL)
    keys.add(NUMBER_KEY_TILT_EXTERNAL_VALUE_DAY)
    keys.add(NUMBER_KEY_TILT_EXTERNAL_VALUE_NIGHT)
    keys.add(NUMBER_KEY_DAILY_MAX_TEMPERATURE_THRESHOLD)
    keys.add(NUMBER_KEY_DAILY_MIN_TEMPERATURE_THRESHOLD)
    keys.add(TIME_KEY_EVENING_CLOSURE_EXTERNAL_TIME)
    keys.add(TIME_KEY_MORNING_OPENING_EXTERNAL_TIME)
    return keys


#
# is_runtime_configurable_key
#
def is_runtime_configurable_key(key: str) -> bool:
    """Return whether a changed option key can be handled by refresh only.

    Runtime-configurable keys include exact-match global settings and pattern-
    based per-cover hot override keys.

    Args:
        key: Option key to check.

    Returns:
        True if a coordinator refresh is sufficient, False if a full reload is
        required.
    """

    if key in get_runtime_configurable_keys():
        return True

    return key.endswith(f"_{COVER_SFX_WEATHER_HOT_EXTERNAL_CONTROL}") or key.endswith(
        (f"_{COVER_SFX_TILT_EXTERNAL_VALUE_DAY}", f"_{COVER_SFX_TILT_EXTERNAL_VALUE_NIGHT}")
    )


# Mapping from ConfKeys.value strings to ResolvedConfig field names.
# Only entries whose field name differs from the .value need to be listed;
# unlisted keys use their .value as the field name.
_VALUE_TO_FIELD: dict[str, str] = {
    "close_covers_after_sunset": "evening_closure_enabled",
    "close_covers_after_sunset_mode": "evening_closure_mode",
    "close_covers_after_sunset_delay": "evening_closure_time",
    "close_covers_after_sunset_cover_list": "evening_closure_cover_list",
    "close_covers_after_sunset_max_closure": "evening_closure_max_closure",
    "close_covers_after_sunset_ignore_manual_override_duration": "evening_closure_ignore_manual_override_duration",
    "close_covers_after_sunset_keep_closed": "evening_closure_keep_closed",
    "morning_opening_mode": "morning_opening_mode",
    "morning_opening_time": "morning_opening_time",
}


#
# _field_name
#
def _field_name(key: ConfKeys) -> str:
    """Map a ConfKeys value to its ResolvedConfig field name."""

    return _VALUE_TO_FIELD.get(key.value, key.value)


#
# ResolvedConfig
#
@dataclass(frozen=True, slots=True)
class ResolvedConfig:
    automation_disabled_time_range: bool
    automation_disabled_time_range_start: time
    automation_disabled_time_range_end: time
    evening_closure_enabled: bool
    evening_closure_mode: EveningClosureMode
    evening_closure_time: time
    evening_closure_cover_list: tuple[str, ...]
    evening_closure_max_closure: int
    evening_closure_ignore_manual_override_duration: bool
    evening_closure_keep_closed: bool
    morning_opening_mode: MorningOpeningMode
    morning_opening_time: time
    automatic_reopening_mode: ReopeningMode
    covers: tuple[str, ...]
    covers_max_closure: int
    covers_min_closure: int
    covers_min_position_delta: int
    enabled: bool
    lock_mode: LockMode
    manual_override_duration: int
    simulation_mode: bool
    daily_max_temperature_threshold: float
    daily_min_temperature_threshold: float
    sun_azimuth_tolerance: int
    sun_elevation_threshold: float
    tilt_min_change_delta: int
    tilt_open_to_cover_open_delay: int
    tilt_vertical_position: int
    tilt_horizontal_position: int
    tilt_mode_day: TiltMode
    tilt_mode_night: TiltMode
    tilt_set_value_day: int
    tilt_set_value_night: int
    tilt_slat_overlap_ratio: float
    verbose_logging: bool
    weather_entity_id: str
    weather_hot_cutover_time: time

    def get(self, key: ConfKeys) -> Any:
        # Generic access via mapping (field names may differ from ConfKeys values)
        return getattr(self, _field_name(key))

    def as_enum_dict(self) -> dict[ConfKeys, Any]:
        # Build dict without hard-coded names
        return {k: getattr(self, _field_name(k)) for k in ConfKeys}


def resolve(options: Mapping[str, Any] | None) -> ResolvedConfig:
    """Resolve settings from options → defaults using ConfKeys.

    Only shallow keys are considered. Performs light normalization (covers → tuple).
    """
    options = options or {}

    def _val(key: ConfKeys) -> Any:
        spec = CONF_SPECS[key]
        if key.value in options:
            raw = options[key.value]
        elif key is ConfKeys.DAILY_MAX_TEMPERATURE_THRESHOLD and LEGACY_OPTION_KEY_TEMPERATURE_THRESHOLD in options:
            # Backward-compatibility for entries that have not been rewritten by
            # _async_migrate_temperature_threshold_keys yet. Remove this fallback
            # together with that migration once upgrades from pre-rename versions
            # are no longer supported.
            raw = options[LEGACY_OPTION_KEY_TEMPERATURE_THRESHOLD]
        else:
            raw = spec.default
        try:
            return spec.converter(raw)
        except Exception:
            # Fallback safely to default if coercion fails
            return spec.converter(spec.default)

    # Build kwargs dynamically by iterating over ConfKeys, applying light coercion.
    converted: dict[str, Any] = {_field_name(k): _val(k) for k in ConfKeys}

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
