"""Binary sensor platform for smart_cover_automation.

This module provides binary sensors that monitor various aspects of the
Smart Cover Automation integration. The binary sensors provide real-time
status information about the automation system's operation.

The sensors that appear in Home Assistant are:
- Entity: binary_sensor.smart_cover_automation_status - System status monitoring
- Entity: binary_sensor.smart_cover_automation_simulation_mode - Simulation mode status
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .const import (
    BINARY_SENSOR_KEY_STATUS,
    BINARY_SENSOR_KEY_TEMP_HOT,
    BINARY_SENSOR_KEY_WEATHER_SUNNY,
    DOMAIN,
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
    """Set up the binary sensor platform for the integration.

    This function is called by Home Assistant when the integration is loaded.
    It creates and registers all binary sensor entities for the integration.

    Args:
        hass: The Home Assistant instance (unused but required by interface)
        entry: The config entry containing integration configuration and runtime data
        async_add_entities: Callback to register new entities with Home Assistant
    """
    coordinator = entry.runtime_data.coordinator

    # Create all binary sensor entities
    entities = [
        # Status binary sensor - indicates system problems
        StatusBinarySensor(coordinator),
        TempHotBinarySensor(coordinator),
        WeatherSunnyBinarySensor(coordinator),
    ]

    async_add_entities(entities)


class IntegrationBinarySensor(IntegrationEntity, BinarySensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Base binary sensor entity for Smart Cover Automation integration.

    This abstract base class provides common functionality for all binary sensor
    entities in the integration. It handles the basic entity setup and provides
    a foundation for specific binary sensor implementations.

    The class provides:
    - Integration with the coordinator for data updates
    - Automatic availability tracking based on coordinator health
    - Consistent entity naming and identification patterns
    - Integration with Home Assistant's binary sensor platform
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor entity.

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
        #   binary_sensor.smart_cover_automation_{translated_key}
        self._attr_unique_id = f"{DOMAIN}_{entity_description.key}"


#
# StatusBinarySensor
#
class StatusBinarySensor(IntegrationBinarySensor):
    """Binary sensor that reports the integration's health.

    This sensor indicates whether the cover automation system has any issues.
    The sensor's state is automatically derived from the coordinator's operational status.

    State meanings:
    - on: Problem
    - off: OK
    """

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Provides the data for this sensor
        """
        entity_description = BinarySensorEntityDescription(
            key=BINARY_SENSOR_KEY_STATUS,
            translation_key=BINARY_SENSOR_KEY_STATUS,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=BinarySensorDeviceClass.PROBLEM,
        )
        super().__init__(coordinator, entity_description)

    @property
    def is_on(self) -> bool:  # pyright: ignore
        """Return True if the integration has problems."""
        return not self.coordinator.last_update_success


#
# TempHotBinarySensor
#
class TempHotBinarySensor(IntegrationBinarySensor):
    """Binary sensor that reports whether it's a hot day.

    State meanings:
    - on: Hot day
    - off: Not a hot day
    """

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Provides the data for this sensor
        """
        entity_description = BinarySensorEntityDescription(
            key=BINARY_SENSOR_KEY_TEMP_HOT,
            translation_key=BINARY_SENSOR_KEY_TEMP_HOT,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=BinarySensorDeviceClass.HEAT,
        )
        super().__init__(coordinator, entity_description)

    @property
    def is_on(self) -> bool:  # pyright: ignore
        """Return True if it's a hot day."""
        if self.coordinator.data and "temp_hot" in self.coordinator.data:
            return self.coordinator.data["temp_hot"]
        else:
            return False


#
# WeatherSunnyBinarySensor
#
class WeatherSunnyBinarySensor(IntegrationBinarySensor):
    """Binary sensor that reports if the weather is sunny.

    State meanings:
    - on: Sunny
    - off: Not sunny
    """

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Provides the data for this sensor
        """
        entity_description = BinarySensorEntityDescription(
            key=BINARY_SENSOR_KEY_WEATHER_SUNNY,
            translation_key=BINARY_SENSOR_KEY_WEATHER_SUNNY,
            entity_category=EntityCategory.DIAGNOSTIC,
            # No suitable device class exists for sunny weather - using icon instead
            icon="mdi:weather-sunny",
        )
        super().__init__(coordinator, entity_description)

    @property
    def is_on(self) -> bool:  # pyright: ignore
        """Return True if the weather is sunny."""
        if self.coordinator.data and "weather_sunny" in self.coordinator.data:
            return self.coordinator.data["weather_sunny"]
        else:
            return False
