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

from .config import ConfKeys, ResolvedConfig, resolve_entry
from .const import (
    ATTR_AUTOMATION_ENABLED,
    ATTR_COVERS_NUM_MOVED,
    ATTR_COVERS_NUM_TOTAL,
    ATTR_MIN_POSITION_DELTA,
    ATTR_SUN_AZIMUTH,
    ATTR_SUN_ELEVATION,
    ATTR_SUN_ELEVATION_THRESH,
    ATTR_TEMP_CURRENT,
    ATTR_TEMP_HYSTERESIS,
    ATTR_TEMP_MAX_THRESH,
    ATTR_TEMP_MIN_THRESH,
    ATTR_TEMP_SENSOR_ENTITY_ID,
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
        covers: dict[str, dict[str, Any]] = self.coordinator.data.get(ConfKeys.COVERS.value) or {}
        for data in covers.values():
            if key in data:
                return data.get(key)
        return None

    @cached_property
    def native_value(self) -> str | None:  # type: ignore[override]
        resolved: ResolvedConfig = resolve_entry(self.coordinator.config_entry)
        if not bool(resolved.enabled):
            return "Disabled"
        covers: dict[str, dict[str, Any]] = self.coordinator.data.get(ConfKeys.COVERS.value) or {}
        total = len(covers)
        moved = sum(
            1 for d in covers.values() if d.get("desired_position") is not None and d.get("current_position") != d.get("desired_position")
        )

        parts: list[str] = []
        current_temp = self._first_cover_value(ATTR_TEMP_CURRENT)
        if isinstance(current_temp, (int, float)):
            min_temp = resolve_entry(self.coordinator.config_entry).min_temperature
            max_temp = resolve_entry(self.coordinator.config_entry).max_temperature
            parts.append(
                f"Temp {float(current_temp):.1f}°C"
                + (
                    f" in [{float(min_temp):.1f}–{float(max_temp):.1f}]"
                    if isinstance(min_temp, (int, float)) and isinstance(max_temp, (int, float))
                    else ""
                )
            )
        elevation = self._first_cover_value(ATTR_SUN_ELEVATION)
        azimuth = self._first_cover_value(ATTR_SUN_AZIMUTH)
        if isinstance(elevation, (int, float)) and isinstance(azimuth, (int, float)):
            parts.append(f"Sun elev {float(elevation):.1f}°, az {float(azimuth):.0f}°")
        prefix = " • ".join(parts) if parts else "Combined"
        return f"{prefix} • moves {moved}/{total}"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # type: ignore[override]
        resolved: ResolvedConfig = resolve_entry(self.coordinator.config_entry)
        covers: dict[str, dict[str, Any]] = self.coordinator.data.get(ConfKeys.COVERS.value) or {}

        enabled = bool(resolved.enabled)
        temp_hyst = float(resolved.temperature_hysteresis)
        min_delta = int(float(resolved.min_position_delta))
        attrs: dict[str, Any] = {
            ATTR_AUTOMATION_ENABLED: enabled,
            ATTR_COVERS_NUM_TOTAL: len(covers),
            ATTR_COVERS_NUM_MOVED: sum(
                1
                for d in covers.values()
                if d.get("desired_position") is not None and d.get("current_position") != d.get("desired_position")
            ),
            ATTR_TEMP_HYSTERESIS: temp_hyst,
            ATTR_MIN_POSITION_DELTA: min_delta,
        }

        # Combined-only attributes
        attrs.update(
            {
                # Temperature-related
                ATTR_TEMP_SENSOR_ENTITY_ID: resolved.temp_sensor_entity_id,
                ATTR_TEMP_MIN_THRESH: resolved.min_temperature,
                ATTR_TEMP_MAX_THRESH: resolved.max_temperature,
                ATTR_TEMP_CURRENT: self._first_cover_value(ATTR_TEMP_CURRENT),
                # Sun-related
                ATTR_SUN_ELEVATION: self._first_cover_value(ATTR_SUN_ELEVATION),
                ATTR_SUN_AZIMUTH: self._first_cover_value(ATTR_SUN_AZIMUTH),
                ATTR_SUN_ELEVATION_THRESH: resolved.sun_elevation_threshold,
                ConfKeys.MAX_CLOSURE.value: int(float(resolved.max_closure)),
            }
        )

        # Include per-cover snapshots for debugging/visibility
        attrs[ConfKeys.COVERS.value] = covers
        return attrs
