"""Sensor platform for smart_cover_automation.

This module provides sensors that monitor various aspects of the
Smart Cover Automation integration. The sensors provide real-time
information about the automation system's operation.

The sensors that appear in Home Assistant are:
- Entity: sensor.smart_cover_automation_last_movement_timestamp - Timestamp of last cover movement
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory, UnitOfTemperature

from .const import (
    DOMAIN,
    SENSOR_KEY_SUN_AZIMUTH,
    SENSOR_KEY_SUN_ELEVATION,
    SENSOR_KEY_TEMP_CURRENT_MAX,
    SENSOR_KEY_TEMP_THRESHOLD,
)
from .entity import IntegrationEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import DataUpdateCoordinator
    from .data import IntegrationConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform for the integration.

    This function is called by Home Assistant when the integration is loaded.
    It creates and registers all sensor entities for the integration.

    Args:
        hass: The Home Assistant instance (unused but required by interface)
        entry: The config entry containing integration configuration and runtime data
        async_add_entities: Callback to register new entities with Home Assistant
    """
    coordinator = entry.runtime_data.coordinator

    # Create all sensor entities
    entities = [
        SunAzimuthSensor(coordinator),
        SunElevationSensor(coordinator),
        TempCurrentMaxSensor(coordinator),
        TempThresholdSensor(coordinator),
    ]

    async_add_entities(entities)


#
# IntegrationSensor
#
class IntegrationSensor(IntegrationEntity, SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Base sensor entity for Smart Cover Automation integration.

    This abstract base class provides common functionality for all sensor
    entities in the integration. It handles the basic entity setup and provides
    a foundation for specific sensor implementations.

    The class provides:
    - Integration with the coordinator for data updates
    - Automatic availability tracking based on coordinator health
    - Consistent entity naming and identification patterns
    - Integration with Home Assistant's sensor platform
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                         and provides data for this sensor
            entity_description: Configuration describing the entity's properties
                                (name, device class, etc.)
        """
        # Initialize the base entity with coordinator integration
        super().__init__(coordinator)

        # Store the entity description that defines this sensor's characteristics
        self.entity_description = entity_description

        # Override the unique ID or HA uses the device class instead of the key.
        # Expected resulting entity_id pattern:
        #   sensor.smart_cover_automation_{translated_key}
        self._attr_unique_id = f"{DOMAIN}_{entity_description.key}"

    # Note: Multiple inheritance from IntegrationEntity (CoordinatorEntity) and
    # SensorEntity causes a Pylance conflict on the 'available' property.
    # Both base classes define it differently, but they're compatible at runtime.
    # The CoordinatorEntity's implementation provides the correct coordinator-based
    # availability logic we want, so no override is needed.


#
# SunAzimuthSensor
#
class SunAzimuthSensor(IntegrationSensor):
    """Sensor that reports the current sun azimuth angle."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Provides the data for this sensor
        """
        entity_description = SensorEntityDescription(
            key=SENSOR_KEY_SUN_AZIMUTH,
            translation_key=SENSOR_KEY_SUN_AZIMUTH,
            entity_category=EntityCategory.DIAGNOSTIC,
            # No suitable device class exists for angles - using icon instead
            # We're not setting state_class (SensorStateClass) to avoid cluttering long-term statistics
            icon="mdi:sun-compass",
            native_unit_of_measurement="°",
        )
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self) -> float | None:  # pyright: ignore
        """Return the current sun azimuth angle in degrees.

        Returns:
            Float representing the sun's azimuth angle (0° to 360°),
            or None if sun position data is unavailable.
        """
        if self.coordinator.data and "sun_azimuth" in self.coordinator.data:
            return self.coordinator.data["sun_azimuth"]
        else:
            return None


#
# SunElevationSensor
#
class SunElevationSensor(IntegrationSensor):
    """Sensor that reports the current sun elevation angle."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Provides the data for this sensor
        """
        entity_description = SensorEntityDescription(
            key=SENSOR_KEY_SUN_ELEVATION,
            translation_key=SENSOR_KEY_SUN_ELEVATION,
            entity_category=EntityCategory.DIAGNOSTIC,
            # No suitable device class exists for angles - using icon instead
            # We're not setting state_class (SensorStateClass) to avoid cluttering long-term statistics
            icon="mdi:sun-angle-outline",
            native_unit_of_measurement="°",
        )
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self) -> float | None:  # pyright: ignore
        """Return the current sun elevation angle in degrees.

        Returns:
            Float representing the sun's elevation angle (min. -90° at nadir to max. +90° at zenith),
            or None if sun position data is unavailable.
        """
        if self.coordinator.data and "sun_elevation" in self.coordinator.data:
            return self.coordinator.data["sun_elevation"]
        else:
            return None


#
# TempCurrentMaxSensor
#
class TempCurrentMaxSensor(IntegrationSensor):
    """Sensor that reports the current maximum temperature."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Provides the data for this sensor
        """
        entity_description = SensorEntityDescription(
            key=SENSOR_KEY_TEMP_CURRENT_MAX,
            translation_key=SENSOR_KEY_TEMP_CURRENT_MAX,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.TEMPERATURE,
            # We're not setting state_class (SensorStateClass) to avoid cluttering long-term statistics
            icon="mdi:thermometer-chevron-up",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        )
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self) -> float | None:  # pyright: ignore
        """Return the current maximum temperature.

        Returns:
            Float representing the current maximum temperature in degrees Celsius,
            or None if that is unavailable.
        """
        if self.coordinator.data and "temp_current_max" in self.coordinator.data:
            return self.coordinator.data["temp_current_max"]
        else:
            return None


#
# TempThresholdSensor
#
class TempThresholdSensor(IntegrationSensor):
    """Sensor that reports the configured threshold temperature."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Provides the data for this sensor
        """
        entity_description = SensorEntityDescription(
            key=SENSOR_KEY_TEMP_THRESHOLD,
            translation_key=SENSOR_KEY_TEMP_THRESHOLD,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.TEMPERATURE,
            # We're not setting state_class (SensorStateClass) to avoid cluttering long-term statistics
            icon="mdi:thermometer-lines",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        )
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self) -> float:  # pyright: ignore
        """Return the configured threshold temperature.

        Returns:
            Float representing the configured threshold temperature in degrees Celsius.
        """
        resolved = self.coordinator._resolved_settings()
        return resolved.temp_threshold
