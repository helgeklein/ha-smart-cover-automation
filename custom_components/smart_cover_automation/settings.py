"""Typed settings dataclasses for smart_cover_automation.

- The dataclass field names are the single source of truth (e.g., "max_temperature").
- Each setting has a default and an optional current value, accessed via `.current`.
- Class-level `.key` access is supported: `Settings.<field>.key` returns the literal
    field name string. This is implemented via a metaclass that intercepts slotted
    dataclass member descriptors and returns a tiny proxy exposing `.key`.
    At instance level, `Setting.key` remains the explicit string passed to the
    default factory. Treat `Settings.<field>.key` as a constant; in unusual runtimes
    where this cannot be provided, callers can fall back to `KEYS`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from types import MemberDescriptorType
from typing import Any, Generic, Mapping, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class Setting(Generic[T]):
    """A typed setting with a default and an optional override value."""

    default: T
    key: str
    value: T | None = None

    @property
    def current(self) -> T:
        return self.value if self.value is not None else self.default


@dataclass(frozen=True, slots=True)
class _FieldKeyProxy:
    """Lightweight proxy that exposes a 'key' attribute for class-level access."""

    key: str


class _SettingsMeta(type):
    """Metaclass that maps class-level field access to a proxy exposing .key.

    For slotted dataclasses, class attributes are member descriptors. We intercept
    those and return a proxy so code can use `Settings.<field>.key`.
    """

    def __getattribute__(cls, name: str):  # type: ignore[override]
        value = super().__getattribute__(name)
        # If the attribute is a slot member (field), return a proxy with .key
        if isinstance(value, MemberDescriptorType):
            try:
                dataclass_fields = getattr(cls, "__dataclass_fields__", None)
                if dataclass_fields and name in dataclass_fields:
                    return _FieldKeyProxy(key=name)
            except Exception:
                # Fall through to normal value if field lookup fails
                pass
        return value


@dataclass(slots=True)
class Settings(metaclass=_SettingsMeta):
    """All integration settings; field names are the canonical keys.

    Usage:
    - Load: settings = Settings.from_sources(entry.options, entry.data)
    - Read: max_t: float = settings.max_temperature.current
    - Save: await entry.async_set_options(settings.to_options())
    """

    # Field names are the keys used in options and data mappings
    enabled: Setting[bool] = field(default_factory=lambda: Setting(key="enabled", default=True))
    covers: Setting[tuple[str, ...]] = field(default_factory=lambda: Setting(key="covers", default=()))
    temperature_sensor: Setting[str] = field(default_factory=lambda: Setting(key="temperature_sensor", default="sensor.temperature"))
    max_temperature: Setting[float] = field(default_factory=lambda: Setting(key="max_temperature", default=24.0))
    min_temperature: Setting[float] = field(default_factory=lambda: Setting(key="min_temperature", default=21.0))
    temperature_hysteresis: Setting[float] = field(default_factory=lambda: Setting(key="temperature_hysteresis", default=0.5))
    min_position_delta: Setting[int] = field(default_factory=lambda: Setting(key="min_position_delta", default=5))
    sun_elevation_threshold: Setting[float] = field(default_factory=lambda: Setting(key="sun_elevation_threshold", default=20.0))
    max_closure: Setting[int] = field(default_factory=lambda: Setting(key="max_closure", default=100))
    verbose_logging: Setting[bool] = field(default_factory=lambda: Setting(key="verbose_logging", default=False))

    @classmethod
    def from_sources(cls, options: Mapping[str, Any] | None, data: Mapping[str, Any] | None) -> "Settings":
        """Build settings by reading options first, then data.

        Only explicit overrides are stored in the Setting.value fields.
        """
        options = options or {}
        data = data or {}
        inst = cls()
        for f in fields(cls):
            key = f.name
            s: Setting[Any] = getattr(inst, f.name)
            if key in options:
                s.value = cls._normalize_value(key, options[key])
            elif key in data:
                s.value = cls._normalize_value(key, data[key])
        return inst

    def to_options(self) -> dict[str, Any]:
        """Return a dict of explicit overrides suitable for entry.async_set_options.

        Defaults are not persisted; only values explicitly set are included.
        """
        out: dict[str, Any] = {}
        for f in fields(self):
            key = f.name
            val = getattr(self, f.name).value
            if val is not None:
                out[key] = val
        return out

    @staticmethod
    def _normalize_value(key: str, value: Any) -> Any:
        """Normalize certain values to expected types.

        Keeps keys single-sourced; light coercion for types often serialized.
        """
        if key == "covers" and isinstance(value, list):
            # Persist as tuple for immutability
            return tuple(value)
        return value


# Mapping helpers to avoid duplicating string literals in tests and callers
# KEYS maps UPPER_CASE friendly names to the canonical field name strings
# DEFAULTS maps UPPER_CASE names to the default values defined on Settings
KEYS: dict[str, str] = {}
DEFAULTS: dict[str, Any] = {}
_inst = Settings()
for _f in fields(Settings):
    _key = _f.name
    KEYS[_key.upper()] = _key
    _setting: Setting[Any] = getattr(_inst, _key)
    DEFAULTS[_key.upper()] = _setting.default
