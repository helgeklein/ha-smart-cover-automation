"""Sensor platform for smart_cover_automation.

This module provides sensors that monitor various aspects of the
Smart Cover Automation integration. The sensors provide real-time
information about the automation system's operation.

The sensors that appear in Home Assistant are:
- Entity: sensor.smart_cover_automation_last_movement_timestamp - Timestamp of last cover movement
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory

from .config import ConfKeys
from .const import DOMAIN, SENSOR_KEY_LAST_MOVEMENT_TIMESTAMP
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
        # Last movement timestamp sensor - shows when covers were last moved
        LastMovementTimestampSensor(coordinator),
    ]

    async_add_entities(entities)


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


class LastMovementTimestampSensor(IntegrationSensor):
    """Sensor that reports the timestamp of the last cover movement.

    This sensor tracks when any cover in the automation was last moved.
    It provides a timestamp that Home Assistant will automatically format
    according to the user's locale and timezone settings.

    The sensor provides:
    - Timestamp device class for appropriate UI representation
    - Automatic availability tracking based on coordinator health
    - Integration with Home Assistant's sensor platform

    Value meanings:
    - datetime: Most recent timestamp when a cover was moved
    - None: No movements have been recorded yet
    """

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the last movement timestamp sensor.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                         and provides the data for this sensor
        """
        entity_description = SensorEntityDescription(
            key=SENSOR_KEY_LAST_MOVEMENT_TIMESTAMP,
            icon="mdi:clock-outline",
            translation_key=SENSOR_KEY_LAST_MOVEMENT_TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            device_class=SensorDeviceClass.TIMESTAMP,
        )
        super().__init__(coordinator, entity_description)

    @property
    def native_value(self) -> datetime | None:  # pyright: ignore
        """Return the timestamp of the most recent cover movement.

        Returns:
            Datetime object of the most recent movement,
            or None if no movements have been recorded yet.
            Home Assistant will automatically format this according to
            the user's locale and timezone settings.

        Examples:
            datetime(2025, 10, 9, 14, 32, 15, 123456, tzinfo=timezone.utc)
            None (when no movements recorded)
        """
        latest_timestamp: datetime | None = None

        # Iterate through all covers in coordinator data and find the most recent position history entry
        covers = self.coordinator.data.get(ConfKeys.COVERS.value) if self.coordinator.data else {}
        if not isinstance(covers, dict):
            covers = {}
        for entity_id in covers.keys():
            entry = self.coordinator._cover_pos_history_mgr.get_latest_entry(entity_id)

            if not entry or not entry.cover_moved:
                continue

            if latest_timestamp is None or entry.timestamp > latest_timestamp:
                latest_timestamp = entry.timestamp

        return latest_timestamp
