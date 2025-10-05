"""Sensor platform for smart_cover_automation.

Provides an "Automation Status" sensor summarizing the current automation mode and recent activity.
"""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from .config import ConfKeys, ResolvedConfig, resolve_entry
from .const import (
    COVER_ATTR_POS_CURRENT,
    COVER_ATTR_POS_TARGET_FINAL,
    SENSOR_ATTR_AUTOMATION_ENABLED,
    SENSOR_ATTR_COVERS_MAX_CLOSURE_POS,
    SENSOR_ATTR_COVERS_MIN_CLOSURE_POS,
    SENSOR_ATTR_COVERS_MIN_POSITION_DELTA,
    SENSOR_ATTR_COVERS_NUM_MOVED,
    SENSOR_ATTR_COVERS_NUM_TOTAL,
    SENSOR_ATTR_MANUAL_OVERRIDE_DURATION,
    SENSOR_ATTR_SIMULATION_ENABLED,
    SENSOR_ATTR_SUN_AZIMUTH,
    SENSOR_ATTR_SUN_AZIMUTH_TOLERANCE,
    SENSOR_ATTR_SUN_ELEVATION,
    SENSOR_ATTR_SUN_ELEVATION_THRESH,
    SENSOR_ATTR_TEMP_CURRENT_MAX,
    SENSOR_ATTR_TEMP_HOT,
    SENSOR_ATTR_TEMP_THRESHOLD,
    SENSOR_ATTR_WEATHER_ENTITY_ID,
    SENSOR_ATTR_WEATHER_SUNNY,
    SENSOR_KEY_AUTOMATION_STATUS,
)
from .entity import IntegrationEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import DataUpdateCoordinator
    from .data import IntegrationConfigEntry


#
# _count_moved_covers
#
def _count_moved_covers(covers: dict[str, dict[str, Any]]) -> int:
    """Count covers that have been moved (target position differs from current position)."""
    return sum(
        1
        for d in covers.values()
        if d.get(COVER_ATTR_POS_TARGET_FINAL) is not None and d.get(COVER_ATTR_POS_CURRENT) != d.get(COVER_ATTR_POS_TARGET_FINAL)
    )


# Define sensor entity descriptions for the platform
# Only creates the automation status sensor with comprehensive status info
ENTITY_DESCRIPTIONS = (
    # Status sensor - provides comprehensive automation status and metrics
    SensorEntityDescription(
        key=SENSOR_KEY_AUTOMATION_STATUS,
        icon="mdi:information-outline",
        translation_key=SENSOR_KEY_AUTOMATION_STATUS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform.

    Creates the automation status sensor that provides comprehensive
    status information about the smart cover automation system.
    """
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = []

    # Create sensor entities based on the entity descriptions
    for entity_description in ENTITY_DESCRIPTIONS:
        entities.append(
            AutomationStatusSensor(
                coordinator=coordinator,
                entity_description=entity_description,
            )
        )

    async_add_entities(entities)


class AutomationStatusSensor(IntegrationEntity, SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Comprehensive status sensor for smart cover automation.

    This sensor provides a detailed overview of the automation system including:
    - Current temperature and threshold status
    - Sun position (elevation and azimuth)
    - Number of covers moved vs total covers
    - Automation enabled
    - Simulation mode enabled

    The sensor value is a human-readable summary, while detailed metrics
    are provided via extra_state_attributes for use in dashboards and automations.
    """

    def __init__(
        self,
        coordinator: "DataUpdateCoordinator",
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the automation status sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = entity_description.key

    # Note: We inherit the 'available' property from IntegrationEntity/CoordinatorEntity
    # which provides the correct coordinator-based availability logic.
    # No override is needed since the default behavior is exactly what we want.

    #
    # native_value
    #
    @cached_property
    def native_value(self) -> str | None:
        """Return the sensor's main state value as a human-readable summary.

        Provides a concise, human-readable status string that summarizes the current
        automation state. The format varies based on configuration and conditions:

        - "Disabled" - when automation is disabled in configuration
        - "Simulation mode enabled • [details] • moves X/Y" - when simulation mode is active
        - "[temp info] • [sun info] • moves X/Y" - normal operation summary

        The summary includes:
        - Current temperature vs threshold (when available)
        - Sun elevation and azimuth (when available)
        - Number of covers moved vs total covers configured

        Returns:
            A formatted status string, or None if coordinator data is unavailable.

        Examples:
            "Temp 24.5°C, threshold 22.0°C • Sun elev 45.0°, az 180° • moves 2/4"
            "Simulation mode enabled • Temp 26.1°C, threshold 22.0°C • moves 0/2"
            "Disabled"
        """
        if not self.coordinator.data:
            return None

        resolved: ResolvedConfig = resolve_entry(self.coordinator.config_entry)
        if not resolved.enabled:
            return "Disabled"

        # Calculate how many covers have been moved (have desired position != current position)
        covers: dict[str, dict[str, Any]] = self.coordinator.data.get(ConfKeys.COVERS.value) or {}
        total = len(covers)
        moved = _count_moved_covers(covers)

        # Build status components for display
        parts: list[str] = []

        if resolved.simulating:
            parts.append("Simulation mode enabled")

        # Add temperature information if available
        current_temp = self.coordinator.data.get(SENSOR_ATTR_TEMP_CURRENT_MAX)
        if isinstance(current_temp, (int, float)):
            temp_threshold = resolve_entry(self.coordinator.config_entry).temp_threshold
            parts.append(f"Temp {float(current_temp):.1f}°C" + (f", threshold {temp_threshold:.1f}°C"))

        # Add sun position information if available
        elevation = self.coordinator.data.get(SENSOR_ATTR_SUN_ELEVATION)
        azimuth = self.coordinator.data.get(SENSOR_ATTR_SUN_AZIMUTH)
        if isinstance(elevation, (int, float)) and isinstance(azimuth, (int, float)):
            parts.append(f"Sun elev {float(elevation):.1f}°, az {float(azimuth):.0f}°")

        # Combine all parts with cover movement summary
        prefix = " • ".join(parts)
        return f"{prefix} • moves {moved}/{total}"

    #
    # extra_state_attributes
    #
    @cached_property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return detailed sensor state attributes for the automation status.

        Provides comprehensive metrics and configuration values that can be used
        in Home Assistant dashboards, automations, and scripts. Includes:
        - Configuration settings (thresholds, limits, entity IDs)
        - Current environmental conditions (temperature, sun position)
        - Cover statistics (total count, number moved)
        - Raw cover data for debugging

        This is called by HA after coordinator._async_update_data() runs
        to get additional attributes for the integration entity state.
        """

        if not self.coordinator.data:
            return None

        resolved: ResolvedConfig = resolve_entry(self.coordinator.config_entry)
        covers: dict[str, dict[str, Any]] = self.coordinator.data.get(ConfKeys.COVERS.value) or {}

        # Count covers that have been moved
        num_covers_moved = _count_moved_covers(covers)

        # Compile all automation metrics and configuration for external access
        attrs: dict[str, Any] = {
            # Configuration settings
            SENSOR_ATTR_AUTOMATION_ENABLED: resolved.enabled,
            SENSOR_ATTR_COVERS_MAX_CLOSURE_POS: resolved.covers_max_closure,
            SENSOR_ATTR_COVERS_MIN_CLOSURE_POS: resolved.covers_min_closure,
            SENSOR_ATTR_COVERS_MIN_POSITION_DELTA: resolved.covers_min_position_delta,
            SENSOR_ATTR_MANUAL_OVERRIDE_DURATION: resolved.manual_override_duration,
            SENSOR_ATTR_SIMULATION_ENABLED: resolved.simulating,
            SENSOR_ATTR_SUN_AZIMUTH_TOLERANCE: resolved.sun_azimuth_tolerance,
            SENSOR_ATTR_SUN_ELEVATION_THRESH: resolved.sun_elevation_threshold,
            SENSOR_ATTR_TEMP_THRESHOLD: resolved.temp_threshold,
            SENSOR_ATTR_WEATHER_ENTITY_ID: resolved.weather_entity_id,
            # Current statistics
            SENSOR_ATTR_COVERS_NUM_MOVED: num_covers_moved,
            SENSOR_ATTR_COVERS_NUM_TOTAL: len(covers),
            # Environmental data from coordinator
            SENSOR_ATTR_SUN_AZIMUTH: self.coordinator.data.get(SENSOR_ATTR_SUN_AZIMUTH),
            SENSOR_ATTR_SUN_ELEVATION: self.coordinator.data.get(SENSOR_ATTR_SUN_ELEVATION),
            SENSOR_ATTR_TEMP_CURRENT_MAX: self.coordinator.data.get(SENSOR_ATTR_TEMP_CURRENT_MAX),
            SENSOR_ATTR_TEMP_HOT: self.coordinator.data.get(SENSOR_ATTR_TEMP_HOT),
            SENSOR_ATTR_WEATHER_SUNNY: self.coordinator.data.get(SENSOR_ATTR_WEATHER_SUNNY),
        }

        # Include raw per-cover data for debugging and advanced automations
        attrs[ConfKeys.COVERS.value] = covers

        return attrs
