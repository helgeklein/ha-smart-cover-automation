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

from .const import (
    AUTOMATION_TYPE_SUN,
    AUTOMATION_TYPE_TEMPERATURE,
    CONF_AUTOMATION_TYPE,
    CONF_ENABLED,
    CONF_MAX_CLOSURE,
    CONF_MAX_TEMP,
    CONF_MIN_POSITION_DELTA,
    CONF_MIN_TEMP,
    CONF_SUN_ELEVATION_THRESHOLD,
    CONF_TEMP_HYSTERESIS,
    CONF_TEMP_SENSOR,
    DEFAULT_SUN_ELEVATION_THRESHOLD,
    MAX_CLOSURE,
    MIN_POSITION_DELTA,
    TEMP_HYSTERESIS,
)
from .entity import IntegrationEntity

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
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )

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
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )

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
        enabled = config.get(CONF_ENABLED, True)
        if enabled is False:
            return "Disabled"

        automation_type = config.get(CONF_AUTOMATION_TYPE)
        covers: dict[str, dict[str, Any]] = self.coordinator.data.get("covers") or {}
        total = len(covers)
        moved = sum(
            1
            for d in covers.values()
            if d.get("desired_position") is not None
            and d.get("current_position") != d.get("desired_position")
        )

        # Temperature automation summary
        if automation_type == AUTOMATION_TYPE_TEMPERATURE:
            current_temp = self._first_cover_value("current_temp")
            min_temp = config.get(CONF_MIN_TEMP)
            max_temp = config.get(CONF_MAX_TEMP)
            if (
                isinstance(current_temp, (int, float))
                and min_temp is not None
                and max_temp is not None
            ):
                return f"Temp {float(current_temp):.1f}°C in [{float(min_temp):.1f}–{float(max_temp):.1f}] • moves {moved}/{total}"
            return f"Temperature mode • moves {moved}/{total}"

        # Sun automation summary
        if automation_type == AUTOMATION_TYPE_SUN:
            elevation = self._first_cover_value("sun_elevation")
            azimuth = self._first_cover_value("sun_azimuth")
            if isinstance(elevation, (int, float)) and isinstance(
                azimuth, (int, float)
            ):
                return f"Sun elev {float(elevation):.1f}°, az {float(azimuth):.0f}° • moves {moved}/{total}"
            return f"Sun mode • moves {moved}/{total}"

        # Fallback
        return f"Unknown mode • moves {moved}/{total}"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # type: ignore[override]
        config = self.coordinator.config_entry.runtime_data.config
        covers: dict[str, dict[str, Any]] = self.coordinator.data.get("covers") or {}

        automation_type = config.get(CONF_AUTOMATION_TYPE)
        enabled = bool(config.get(CONF_ENABLED, True))
        temp_hyst = float(config.get(CONF_TEMP_HYSTERESIS, TEMP_HYSTERESIS))
        min_delta = int(float(config.get(CONF_MIN_POSITION_DELTA, MIN_POSITION_DELTA)))
        attrs: dict[str, Any] = {
            "enabled": enabled,
            "automation_type": automation_type,
            "covers_total": len(covers),
            "covers_moved": sum(
                1
                for d in covers.values()
                if d.get("desired_position") is not None
                and d.get("current_position") != d.get("desired_position")
            ),
            "temp_hysteresis": temp_hyst,
            "min_position_delta": min_delta,
        }

        if automation_type == AUTOMATION_TYPE_TEMPERATURE:
            attrs.update(
                {
                    "temperature_sensor": config.get(CONF_TEMP_SENSOR),
                    "min_temp": config.get(CONF_MIN_TEMP),
                    "max_temp": config.get(CONF_MAX_TEMP),
                    "current_temp": self._first_cover_value("current_temp"),
                }
            )
        elif automation_type == AUTOMATION_TYPE_SUN:
            attrs.update(
                {
                    "sun_elevation": self._first_cover_value("sun_elevation"),
                    "sun_azimuth": self._first_cover_value("sun_azimuth"),
                    "elevation_threshold": config.get(
                        CONF_SUN_ELEVATION_THRESHOLD, DEFAULT_SUN_ELEVATION_THRESHOLD
                    ),
                    "max_closure": int(
                        float(config.get(CONF_MAX_CLOSURE, MAX_CLOSURE))
                    ),
                }
            )

        # Include per-cover snapshots for debugging/visibility
        attrs["covers"] = covers
        return attrs
