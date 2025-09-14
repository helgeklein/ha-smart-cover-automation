"""Settings registry and resolution for smart_cover_automation.

This module defines a typo-safe enum of setting keys, a registry of specs with
defaults and coercion, and helpers to resolve effective settings from a
ConfigEntry (options → data → defaults).
"""

from __future__ import annotations

from dataclasses import dataclass, fields
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

    Each key corresponds to a setting that can be configured via options or data.
    """

    ENABLED = "enabled"  # Global on/off for all automation.
    COVERS = "covers"  # Tuple of cover entity_ids to control.
    COVERS_MAX_CLOSURE = "covers_max_closure"  # Maximum closure position (0 = fully closed, 100 = fully open)
    COVERS_MIN_POSITION_DELTA = "covers_min_position_delta"  # Ignore smaller position changes (%).
    TEMP_HYSTERESIS = "temp_hysteresis"  # Deadband around thresholds (°C).
    TEMP_SENSOR_ENTITY_ID = "temp_sensor_entity_id"  # Temperature sensor entity_id.
    TEMP_THRESHOLD = "temp_threshold"  # Temperature threshold at which heat protection activates (°C).
    SUN_AZIMUTH_TOLERANCE = "sun_azimuth_tolerance"  # Max angle difference (°) to consider sun hitting.
    SUN_ELEVATION_THRESHOLD = "sun_elevation_threshold"  # Min sun elevation to act (degrees).
    VERBOSE_LOGGING = "verbose_logging"  # Enable DEBUG logs for this entry.


class _Converters:
    """Coercion helpers used by _ConfSpec."""

    @staticmethod
    def to_bool(v: Any) -> bool:
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
            return tuple(v)  # type: ignore[arg-type]
        except Exception:
            return ()


# Type-only aliases so annotations can refer without exporting helpers.
if TYPE_CHECKING:  # pragma: no cover - type checking only
    Converters = _Converters
    ConfSpec = _ConfSpec


# Central registry of settings with defaults and coercion (type conversion).
# This is the single source of truth for all settings keys and their types.
CONF_SPECS: dict[ConfKeys, _ConfSpec] = {
    ConfKeys.ENABLED: _ConfSpec(default=True, converter=_Converters.to_bool),
    ConfKeys.COVERS: _ConfSpec(default=(), converter=_Converters.to_covers_tuple),
    ConfKeys.COVERS_MAX_CLOSURE: _ConfSpec(default=0, converter=_Converters.to_int),
    ConfKeys.COVERS_MIN_POSITION_DELTA: _ConfSpec(default=5, converter=_Converters.to_int),
    ConfKeys.TEMP_HYSTERESIS: _ConfSpec(default=0.5, converter=_Converters.to_float),
    ConfKeys.TEMP_SENSOR_ENTITY_ID: _ConfSpec(default="sensor.temperature", converter=_Converters.to_str),
    ConfKeys.TEMP_THRESHOLD: _ConfSpec(default=23.0, converter=_Converters.to_float),
    ConfKeys.SUN_AZIMUTH_TOLERANCE: _ConfSpec(default=90, converter=_Converters.to_int),
    ConfKeys.SUN_ELEVATION_THRESHOLD: _ConfSpec(default=20.0, converter=_Converters.to_float),
    ConfKeys.VERBOSE_LOGGING: _ConfSpec(default=False, converter=_Converters.to_bool),
}

# Public API of this module (keep helper class internal)
__all__ = [
    "ConfKeys",
    "CONF_SPECS",
    "ResolvedConfig",
    "validate_settings_contract",
    "resolve",
    "resolve_entry",
]


# Simple, explicit settings structure resolved from options → data → defaults.
# This provides a lightweight alternative to the descriptor-based Settings above
# without changing existing callers. Consumers can migrate to this over time.
@dataclass(frozen=True, slots=True)
class ResolvedConfig:
    enabled: bool
    covers: tuple[str, ...]
    covers_max_closure: int
    covers_min_position_delta: int
    temp_hysteresis: float
    temp_sensor_entity_id: str
    temp_threshold: float
    sun_azimuth_tolerance: int
    sun_elevation_threshold: float
    verbose_logging: bool

    def get(self, key: ConfKeys) -> Any:
        # Generic access: ConfKeys values match dataclass field names
        return getattr(self, key.value)

    def as_enum_dict(self) -> dict[ConfKeys, Any]:
        # Build dict without hard-coded names
        return {k: getattr(self, k.value) for k in ConfKeys}


def validate_settings_contract() -> None:
    """Validate ConfKeys, CONF_SPECS and ResolvedConfig stay in sync.

    Raises AssertionError with a clear message if there is any mismatch.
    """
    enum_names = {k.value for k in ConfKeys}
    spec_names = {k.value for k in CONF_SPECS.keys()}
    dc_names = {f.name for f in fields(ResolvedConfig)}

    errors: list[str] = []
    if enum_names != spec_names:
        errors.append(
            f"ConfKeys vs CONF_SPECS mismatch: missing_in_specs={enum_names - spec_names}, extra_in_specs={spec_names - enum_names}"
        )
    if enum_names != dc_names:
        errors.append(f"ConfKeys vs ResolvedConfig mismatch: missing_in_dc={enum_names - dc_names}, extra_in_dc={dc_names - enum_names}")
    # Ensure no None defaults are present
    none_defaults = [k.value for k, spec in CONF_SPECS.items() if spec.default is None]
    if none_defaults:
        errors.append(f"None defaults found in CONF_SPECS: {none_defaults}")

    if errors:
        raise AssertionError(" | ".join(errors))


def resolve(options: Mapping[str, Any] | None, data: Mapping[str, Any] | None) -> ResolvedConfig:
    """Resolve settings from options → data → defaults using ConfKeys.

    Only shallow keys are considered. Performs light normalization (covers → tuple).
    """
    options = options or {}
    data = data or {}

    # Enforce contract consistency during resolution for clear failures in dev/CI
    validate_settings_contract()

    def _val(key: ConfKeys) -> Any:
        spec = CONF_SPECS[key]
        if key.value in options:
            raw = options[key.value]
        elif key.value in data:
            raw = data[key.value]
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

    Accepts any object with 'options' and 'data' attributes (works with test mocks).
    """
    opts = getattr(entry, HA_OPTIONS, None) or {}
    dat = getattr(entry, "data", None) or {}
    return resolve(opts, dat)
