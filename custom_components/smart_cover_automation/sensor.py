"""Sensor platform for smart_cover_automation.

Provides:
- An "Integration Sensor" that mirrors a text body from the coordinator (used by tests/demo).
- An "Automation Status" sensor summarizing the current automation mode and recent outcomes.

Availability and native_value are provided via cached properties to align with
modern Home Assistant entity patterns.
"""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from . import const
from .entity import IntegrationEntity
from .settings import Settings

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import DataUpdateCoordinator
    from .data import IntegrationConfigEntry

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="smart_cover_automation",
        name="Integration Sensor",
        icon="mdi:format-quote-close",
    ),
    SensorEntityDescription(
        key="automation_status",
        name="Automation Status",
        icon="mdi:information-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = []

    for entity_description in ENTITY_DESCRIPTIONS:
        if entity_description.key == "automation_status":
            entities.append(
                AutomationStatusSensor(
                    coordinator=coordinator,
                    entity_description=entity_description,
                )
            )
        else:
            entities.append(
                IntegrationSensor(
                    coordinator=coordinator,
                    entity_description=entity_description,
                )
            )

    async_add_entities(entities)


class IntegrationSensor(IntegrationEntity, SensorEntity):
    """smart_cover_automation Sensor class."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        # Ensure unique IDs are unique per entity within the platform
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{entity_description.key}"

    @cached_property
    def available(self) -> bool | None:  # type: ignore[override]
        """Return availability; unify base class types for type checkers."""
        return super().available

    @cached_property
    def native_value(self) -> str | None:  # type: ignore[override]
        """Return the native value of the sensor."""
        return self.coordinator.data.get("body")


class AutomationStatusSensor(IntegrationEntity, SensorEntity):
    """A sensor that summarizes the automation status and last outcome."""

    def __init__(
        self,
        coordinator: "DataUpdateCoordinator",
        entity_description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{entity_description.key}"

    @cached_property
    def available(self) -> bool | None:  # type: ignore[override]
        return super().available

    def _first_cover_value(self, key: str) -> Any | None:
        covers: dict[str, dict[str, Any]] = self.coordinator.data.get("covers") or {}
        for data in covers.values():
            if key in data:
                return data.get(key)
        return None

    @cached_property
    def native_value(self) -> str | None:  # type: ignore[override]
        config = self.coordinator.config_entry.runtime_data.config
        settings_obj = getattr(self.coordinator.config_entry.runtime_data, "settings", None)
        if isinstance(settings_obj, Settings) and settings_obj.enabled.value is not None:
            enabled = settings_obj.enabled.current
        else:
            enabled = config.get(const.CONF_ENABLED, True)
        if enabled is False:
            return "Disabled"
        covers: dict[str, dict[str, Any]] = self.coordinator.data.get("covers") or {}
        total = len(covers)
        moved = sum(
            1 for d in covers.values() if d.get("desired_position") is not None and d.get("current_position") != d.get("desired_position")
        )
        # Combined summary (only supported mode)
        parts: list[str] = []
        current_temp = self._first_cover_value("current_temp")
        if isinstance(current_temp, (int, float)):
            settings2 = getattr(self.coordinator.config_entry.runtime_data, "settings", None)
            if isinstance(settings2, Settings) and settings2.min_temperature.value is not None:
                min_temp = settings2.min_temperature.current
            else:
                min_temp = config.get(const.CONF_MIN_TEMP, const.DEFAULT_MIN_TEMP)
            if isinstance(settings2, Settings) and settings2.max_temperature.value is not None:
                max_temp = settings2.max_temperature.current
            else:
                max_temp = config.get("max_temperature", const.DEFAULT_MAX_TEMP)
            parts.append(
                f"Temp {float(current_temp):.1f}°C"
                + (
                    f" in [{float(min_temp):.1f}–{float(max_temp):.1f}]"
                    if isinstance(min_temp, (int, float)) and isinstance(max_temp, (int, float))
                    else ""
                )
            )
        elevation = self._first_cover_value("sun_elevation")
        azimuth = self._first_cover_value("sun_azimuth")
        if isinstance(elevation, (int, float)) and isinstance(azimuth, (int, float)):
            parts.append(f"Sun elev {float(elevation):.1f}°, az {float(azimuth):.0f}°")
        prefix = " • ".join(parts) if parts else "Combined"
        return f"{prefix} • moves {moved}/{total}"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # type: ignore[override]
        config = self.coordinator.config_entry.runtime_data.config
        settings_obj = getattr(self.coordinator.config_entry.runtime_data, "settings", None)
        covers: dict[str, dict[str, Any]] = self.coordinator.data.get("covers") or {}

        if isinstance(settings_obj, Settings) and settings_obj.enabled.value is not None:
            enabled = bool(settings_obj.enabled.current)
        else:
            enabled = bool(config.get(const.CONF_ENABLED, True))
        if isinstance(settings_obj, Settings) and settings_obj.temperature_hysteresis.value is not None:
            temp_hyst = float(settings_obj.temperature_hysteresis.current)
        else:
            temp_hyst = float(config.get(const.CONF_TEMP_HYSTERESIS, const.TEMP_HYSTERESIS))
        if isinstance(settings_obj, Settings) and settings_obj.min_position_delta.value is not None:
            min_delta = int(float(settings_obj.min_position_delta.current))
        else:
            min_delta = int(float(config.get(const.CONF_MIN_POSITION_DELTA, const.MIN_POSITION_DELTA)))
        attrs: dict[str, Any] = {
            "enabled": enabled,
            "covers_total": len(covers),
            "covers_moved": sum(
                1
                for d in covers.values()
                if d.get("desired_position") is not None and d.get("current_position") != d.get("desired_position")
            ),
            "temp_hysteresis": temp_hyst,
            "min_position_delta": min_delta,
        }

        # Combined-only attributes
        attrs.update(
            {
                # Temperature-related
                "temperature_sensor": (
                    settings_obj.temperature_sensor.current
                    if isinstance(settings_obj, Settings) and settings_obj.temperature_sensor.value is not None
                    else config.get(const.CONF_TEMP_SENSOR, const.DEFAULT_TEMP_SENSOR)
                ),
                "min_temp": (
                    settings_obj.min_temperature.current
                    if isinstance(settings_obj, Settings) and settings_obj.min_temperature.value is not None
                    else config.get(const.CONF_MIN_TEMP, const.DEFAULT_MIN_TEMP)
                ),
                "max_temp": (
                    settings_obj.max_temperature.current
                    if isinstance(settings_obj, Settings) and settings_obj.max_temperature.value is not None
                    else config.get("max_temperature", const.DEFAULT_MAX_TEMP)
                ),
                "current_temp": self._first_cover_value("current_temp"),
                # Sun-related
                "sun_elevation": self._first_cover_value("sun_elevation"),
                "sun_azimuth": self._first_cover_value("sun_azimuth"),
                "elevation_threshold": (
                    settings_obj.sun_elevation_threshold.current
                    if isinstance(settings_obj, Settings) and settings_obj.sun_elevation_threshold.value is not None
                    else config.get(const.CONF_SUN_ELEVATION_THRESHOLD, const.DEFAULT_SUN_ELEVATION_THRESHOLD)
                ),
                "max_closure": int(
                    float(
                        (
                            settings_obj.max_closure.current
                            if isinstance(settings_obj, Settings) and settings_obj.max_closure.value is not None
                            else config.get(const.CONF_MAX_CLOSURE, const.DEFAULT_MAX_CLOSURE)
                        )
                    )
                ),
            }
        )

        # Include per-cover snapshots for debugging/visibility
        attrs["covers"] = covers
        return attrs
