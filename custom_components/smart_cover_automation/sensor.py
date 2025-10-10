"""Sensor platform for smart_cover_automation.

Provides a timestamp sensor showing when covers were last moved.
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


#
# _get_last_movement_timestamp
#
def _get_last_movement_timestamp(coordinator: "DataUpdateCoordinator") -> datetime | None:
    """Get the timestamp of the most recent cover movement across all covers.

    Args:
        coordinator: The DataUpdateCoordinator instance

    Returns:
        Datetime object of the most recent movement, or None if no movements recorded
    """
    latest_timestamp: datetime | None = None

    # Iterate through all covers in coordinator data and find the most recent position history entry
    covers = coordinator.data.get(ConfKeys.COVERS.value) if coordinator.data else {}
    if not isinstance(covers, dict):
        covers = {}
    for entity_id in covers.keys():
        entry = coordinator._cover_pos_history_mgr.get_latest_entry(entity_id)

        if not entry or not entry.cover_moved:
            continue

        if latest_timestamp is None or entry.timestamp > latest_timestamp:
            latest_timestamp = entry.timestamp

    return latest_timestamp


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform for the integration.

    This function is called by Home Assistant when the integration is loaded.
    It creates and registers the last movement timestamp sensor.

    Args:
        hass: The Home Assistant instance (unused but required by interface)
        entry: The config entry containing integration configuration and runtime data
        async_add_entities: Callback to register new entities with Home Assistant
    """
    # Create the last movement timestamp sensor
    entity_description = SensorEntityDescription(
        key=SENSOR_KEY_LAST_MOVEMENT_TIMESTAMP,
        icon="mdi:clock-outline",
        translation_key=SENSOR_KEY_LAST_MOVEMENT_TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
    )

    async_add_entities(
        [
            LastMovementTimestampSensor(
                coordinator=entry.runtime_data.coordinator,
                entity_description=entity_description,
            )
        ]
    )


class LastMovementTimestampSensor(IntegrationEntity, SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Sensor that reports the timestamp of the last cover movement.

    This sensor tracks when any cover in the automation was last moved,
    providing a simple timestamp value for monitoring activity.
    The timestamp is in ISO 8601 format (YYYY-MM-DDTHH:MM:SS.mmmmmm+HH:MM).
    """

    def __init__(
        self,
        coordinator: "DataUpdateCoordinator",
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the last movement timestamp sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{DOMAIN}_{entity_description.key}"

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
        return _get_last_movement_timestamp(self.coordinator)
