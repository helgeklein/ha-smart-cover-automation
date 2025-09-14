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

from homeassistant.components.cover import ATTR_CURRENT_POSITION
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from .config import ConfKeys, ResolvedConfig, resolve_entry
from .const import (
    COVER_ATTR_POSITION_DESIRED,
    KEY_BODY,
    SENSOR_ATTR_AUTOMATION_ENABLED,
    SENSOR_ATTR_COVERS_MAX_CLOSURE_POS,
    SENSOR_ATTR_COVERS_MIN_POSITION_DELTA,
    SENSOR_ATTR_COVERS_NUM_MOVED,
    SENSOR_ATTR_COVERS_NUM_TOTAL,
    SENSOR_ATTR_SUN_AZIMUTH,
    SENSOR_ATTR_SUN_ELEVATION,
    SENSOR_ATTR_SUN_ELEVATION_THRESH,
    SENSOR_ATTR_TEMP_CURRENT,
    SENSOR_ATTR_TEMP_HOT,
    SENSOR_ATTR_TEMP_HYSTERESIS,
    SENSOR_ATTR_TEMP_SENSOR_ENTITY_ID,
    SENSOR_ATTR_TEMP_THRESHOLD,
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
        return self.coordinator.data.get(KEY_BODY)


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

    @cached_property
    def native_value(self) -> str | None:  # type: ignore[override]
        if not self.coordinator.data:
            return None

        resolved: ResolvedConfig = resolve_entry(self.coordinator.config_entry)
        if not resolved.enabled:
            return "Disabled"

        covers: dict[str, dict[str, Any]] = self.coordinator.data.get(ConfKeys.COVERS.value) or {}
        total = len(covers)
        moved = sum(
            1
            for d in covers.values()
            if d.get(COVER_ATTR_POSITION_DESIRED) is not None and d.get(ATTR_CURRENT_POSITION) != d.get(COVER_ATTR_POSITION_DESIRED)
        )

        parts: list[str] = []
        current_temp = self.coordinator.data.get(SENSOR_ATTR_TEMP_CURRENT)
        if isinstance(current_temp, (int, float)):
            temp_threshold = resolve_entry(self.coordinator.config_entry).temp_threshold
            parts.append(f"Temp {float(current_temp):.1f}°C" + (f", threshold {temp_threshold:.1f}°C"))
        elevation = self.coordinator.data.get(SENSOR_ATTR_SUN_ELEVATION)
        azimuth = self.coordinator.data.get(SENSOR_ATTR_SUN_AZIMUTH)
        if isinstance(elevation, (int, float)) and isinstance(azimuth, (int, float)):
            parts.append(f"Sun elev {float(elevation):.1f}°, az {float(azimuth):.0f}°")
        prefix = " • ".join(parts) if parts else "Combined"
        return f"{prefix} • moves {moved}/{total}"

    #
    # extra_state_attributes
    #
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # type: ignore[override]
        """Return sensor state attributes.

        This is called by HA after coordinator._async_update_data() runs
        to get additional attributes for the integration entity state.
        """

        if not self.coordinator.data:
            return None

        resolved: ResolvedConfig = resolve_entry(self.coordinator.config_entry)
        covers: dict[str, dict[str, Any]] = self.coordinator.data.get(ConfKeys.COVERS.value) or {}

        num_covers_moved = sum(
            1
            for d in covers.values()
            if d.get(COVER_ATTR_POSITION_DESIRED) is not None and d.get(ATTR_CURRENT_POSITION) != d.get(COVER_ATTR_POSITION_DESIRED)
        )

        # Store sensor attributes
        attrs: dict[str, Any] = {
            SENSOR_ATTR_AUTOMATION_ENABLED: resolved.enabled,
            SENSOR_ATTR_COVERS_MAX_CLOSURE_POS: resolved.covers_max_closure,
            SENSOR_ATTR_COVERS_MIN_POSITION_DELTA: resolved.covers_min_position_delta,
            SENSOR_ATTR_COVERS_NUM_MOVED: num_covers_moved,
            SENSOR_ATTR_COVERS_NUM_TOTAL: len(covers),
            SENSOR_ATTR_SUN_AZIMUTH: self.coordinator.data.get(SENSOR_ATTR_SUN_AZIMUTH),
            SENSOR_ATTR_SUN_ELEVATION: self.coordinator.data.get(SENSOR_ATTR_SUN_ELEVATION),
            SENSOR_ATTR_SUN_ELEVATION_THRESH: resolved.sun_elevation_threshold,
            SENSOR_ATTR_TEMP_CURRENT: self.coordinator.data.get(SENSOR_ATTR_TEMP_CURRENT),
            SENSOR_ATTR_TEMP_HOT: self.coordinator.data.get(SENSOR_ATTR_TEMP_HOT),
            SENSOR_ATTR_TEMP_HYSTERESIS: resolved.temp_hysteresis,
            SENSOR_ATTR_TEMP_SENSOR_ENTITY_ID: resolved.temp_sensor_entity_id,
            SENSOR_ATTR_TEMP_THRESHOLD: resolved.temp_threshold,
        }

        # Include per-cover attributes for debugging/visibility
        attrs[ConfKeys.COVERS.value] = covers

        return attrs
