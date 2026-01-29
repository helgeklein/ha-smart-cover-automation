"""Sensor platform for smart_cover_automation.

This module provides sensors that monitor various aspects of the
Smart Cover Automation integration. The sensors provide real-time
information about the automation system's operation.

The sensors that appear in Home Assistant are:
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory, UnitOfTemperature

from .const import (
    SENSOR_KEY_AUTOMATION_DISABLED_TIME_RANGE,
    SENSOR_KEY_CLOSE_COVERS_AFTER_SUNSET_DELAY,
    SENSOR_KEY_SUN_AZIMUTH,
    SENSOR_KEY_SUN_ELEVATION,
    SENSOR_KEY_TEMP_CURRENT_MAX,
)
from .entity import IntegrationEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import DataUpdateCoordinator
    from .data import IntegrationConfigEntry


#
# async_setup_entry
#
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
        AutomationDisabledTimeRangeSensor(coordinator),
        CloseCoversAfterSunsetDelaySensor(coordinator),
        SunAzimuthSensor(coordinator),
        SunElevationSensor(coordinator),
        TempCurrentMaxSensor(coordinator),
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

    #
    # __init__
    #
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
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_description.key}"

    # Note: Multiple inheritance from IntegrationEntity (CoordinatorEntity) and
    # SensorEntity causes a Pylance conflict on the 'available' property.
    # Both base classes define it differently, but they're compatible at runtime.
    # The CoordinatorEntity's implementation provides the correct coordinator-based
    # availability logic we want, so no override is needed.


#
# AutomationDisabledTimeRangeSensor
#
class AutomationDisabledTimeRangeSensor(IntegrationSensor):
    """Sensor that reports the configured automation disabled time range.

    The sensor displays:
    - "off" when the time range feature is disabled
    - "start-end" (e.g., "22:00-06:00") when the time range feature is enabled
    """

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Provides the data for this sensor
        """
        entity_description = SensorEntityDescription(
            key=SENSOR_KEY_AUTOMATION_DISABLED_TIME_RANGE,
            translation_key=SENSOR_KEY_AUTOMATION_DISABLED_TIME_RANGE,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:clock-time-eight",
        )
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self) -> str:  # pyright: ignore
        """Return the automation disabled time range as a formatted string.

        Returns:
            Translation key "off" if the feature is disabled, or "HH:MM-HH:MM" format if enabled.
        """
        resolved = self.coordinator._resolved_settings()

        if not resolved.automation_disabled_time_range:
            # Return translation key that will be translated to "Off" in UI
            return "off"

        # Format times as HH:MM
        start_time = resolved.automation_disabled_time_range_start
        end_time = resolved.automation_disabled_time_range_end

        start_str = f"{start_time.hour:02d}:{start_time.minute:02d}"
        end_str = f"{end_time.hour:02d}:{end_time.minute:02d}"

        return f"{start_str}-{end_str}"


#
# CloseCoversAfterSunsetDelaySensor
#
class CloseCoversAfterSunsetDelaySensor(IntegrationSensor):
    """Sensor that reports the configured delay for closing covers after sunset.

    The sensor displays the delay in minutes.
    """

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Provides the data for this sensor
        """

        entity_description = SensorEntityDescription(
            key=SENSOR_KEY_CLOSE_COVERS_AFTER_SUNSET_DELAY,
            translation_key=SENSOR_KEY_CLOSE_COVERS_AFTER_SUNSET_DELAY,
            entity_category=EntityCategory.DIAGNOSTIC,
            icon="mdi:timer-outline",
            native_unit_of_measurement="min",
        )
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self) -> int:  # pyright: ignore
        """Return the configured delay for closing covers after sunset.

        Returns:
            Integer representing the delay in minutes.
        """

        resolved = self.coordinator._resolved_settings()

        # Convert seconds to minutes
        return resolved.close_covers_after_sunset_delay // 60


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
        if self.coordinator.data:
            return self.coordinator.data.sun_azimuth
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
        if self.coordinator.data:
            return self.coordinator.data.sun_elevation
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
        if self.coordinator.data:
            return self.coordinator.data.temp_current_max
        else:
            return None
