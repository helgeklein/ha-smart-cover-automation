"""Settings registry and resolution for smart_cover_automation.

This module defines a typo-safe enum of setting keys, a registry of specs with
defaults and coercion, and helpers to resolve effective settings from a
ConfigEntry (options → data → defaults). Legacy classes have been removed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Mapping

# Explicit key/default registry for every setting using an Enum to avoid typos.
# Kept fully explicit and self-contained (no references to other structures).


@dataclass(frozen=True, slots=True)
class SettingSpec:
    key: str
    default: Any
    coerce: Callable[[Any], Any]


class SettingsKey(StrEnum):
    ENABLED = "enabled"
    COVERS = "covers"
    TEMPERATURE_SENSOR = "temperature_sensor"
    MAX_TEMPERATURE = "max_temperature"
    MIN_TEMPERATURE = "min_temperature"
    TEMPERATURE_HYSTERESIS = "temperature_hysteresis"
    MIN_POSITION_DELTA = "min_position_delta"
    SUN_ELEVATION_THRESHOLD = "sun_elevation_threshold"
    MAX_CLOSURE = "max_closure"
    VERBOSE_LOGGING = "verbose_logging"


# Enum-keyed registry; StrEnum members behave like strings for equality/hash
# so accidental plain-string lookups may still work, but use the Enum for safety.
def _to_bool(v: Any) -> bool:
    return bool(v)


def _to_int(v: Any) -> int:
    return int(v)


def _to_float(v: Any) -> float:
    return float(v)


def _to_str(v: Any) -> str:
    return str(v)


def _to_covers_tuple(v: Any) -> tuple[str, ...]:
    if not v:
        return ()
    if isinstance(v, tuple):
        # Convert each element to str defensively
        return tuple(str(x) for x in v)
    if isinstance(v, list):
        return tuple(str(x) for x in v)
    # Fallback: mirror prior behavior (tuple(v)), which turns a string into chars
    try:
        return tuple(v)  # type: ignore[arg-type]
    except Exception:
        return ()


SETTINGS_SPECS: dict[SettingsKey, SettingSpec] = {
    SettingsKey.ENABLED: SettingSpec(key=SettingsKey.ENABLED, default=True, coerce=_to_bool),
    SettingsKey.COVERS: SettingSpec(key=SettingsKey.COVERS, default=(), coerce=_to_covers_tuple),
    SettingsKey.TEMPERATURE_SENSOR: SettingSpec(key=SettingsKey.TEMPERATURE_SENSOR, default="sensor.temperature", coerce=_to_str),
    SettingsKey.MAX_TEMPERATURE: SettingSpec(key=SettingsKey.MAX_TEMPERATURE, default=24.0, coerce=_to_float),
    SettingsKey.MIN_TEMPERATURE: SettingSpec(key=SettingsKey.MIN_TEMPERATURE, default=21.0, coerce=_to_float),
    SettingsKey.TEMPERATURE_HYSTERESIS: SettingSpec(key=SettingsKey.TEMPERATURE_HYSTERESIS, default=0.5, coerce=_to_float),
    SettingsKey.MIN_POSITION_DELTA: SettingSpec(key=SettingsKey.MIN_POSITION_DELTA, default=5, coerce=_to_int),
    SettingsKey.SUN_ELEVATION_THRESHOLD: SettingSpec(key=SettingsKey.SUN_ELEVATION_THRESHOLD, default=20.0, coerce=_to_float),
    SettingsKey.MAX_CLOSURE: SettingSpec(key=SettingsKey.MAX_CLOSURE, default=100, coerce=_to_int),
    SettingsKey.VERBOSE_LOGGING: SettingSpec(key=SettingsKey.VERBOSE_LOGGING, default=False, coerce=_to_bool),
}

# Optional: string-keyed view if consumers prefer plain str keys.
SETTINGS_SPECS_BY_STR: dict[str, SettingSpec] = {k.value: v for k, v in SETTINGS_SPECS.items()}


# Simple, explicit settings structure resolved from options → data → defaults.
# This provides a lightweight alternative to the descriptor-based Settings above
# without changing existing callers. Consumers can migrate to this over time.
@dataclass(frozen=True, slots=True)
class ResolvedSettings:
    enabled: bool
    covers: tuple[str, ...]
    temperature_sensor: str
    max_temperature: float
    min_temperature: float
    temperature_hysteresis: float
    min_position_delta: int
    sun_elevation_threshold: float
    max_closure: int
    verbose_logging: bool

    def get(self, key: SettingsKey) -> Any:
        # Generic access: SettingsKey values match dataclass field names
        return getattr(self, key.value)

    def as_enum_dict(self) -> dict[SettingsKey, Any]:
        # Build dict without hard-coded names
        return {k: getattr(self, k.value) for k in SettingsKey}


def resolve(options: Mapping[str, Any] | None, data: Mapping[str, Any] | None) -> ResolvedSettings:
    """Resolve settings from options → data → defaults using SettingsKey.

    Only shallow keys are considered. Performs light normalization (covers → tuple).
    """
    options = options or {}
    data = data or {}

    def _val(key: SettingsKey) -> Any:
        spec = SETTINGS_SPECS[key]
        if key.value in options:
            raw = options[key.value]
        elif key.value in data:
            raw = data[key.value]
        else:
            raw = spec.default
        try:
            return spec.coerce(raw)
        except Exception:
            # Fallback safely to default if coercion fails
            return spec.coerce(spec.default)

    # Build kwargs dynamically by iterating over SettingsKey, applying light coercion
    values: dict[str, Any] = {k.value: _val(k) for k in SettingsKey}

    return ResolvedSettings(**values)


def resolve_entry(entry: Any) -> ResolvedSettings:
    """Resolve settings directly from a ConfigEntry-like object.

    Accepts any object with 'options' and 'data' attributes (works with test mocks).
    """
    opts = getattr(entry, "options", None) or {}
    dat = getattr(entry, "data", None) or {}
    return resolve(opts, dat)
