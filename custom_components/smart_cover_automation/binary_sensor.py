"""Binary sensor platform for smart_cover_automation.

This module provides a binary sensor that monitors the availability of the
Smart Cover Automation integration. The binary sensor
indicates whether the automation system is functioning properly by reflecting
the coordinator's last update status.

The sensor appears in Home Assistant as:
- Entity: binary_sensor.smart_cover_automation_availability
- Device Class: Connectivity
- States: 'on' (connected/working) or 'off' (disconnected/failed)

This allows users to:
1. Monitor automation system health at a glance
2. Create automations based on system status
3. Troubleshoot issues when cover automation stops working
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .const import DOMAIN
from .entity import IntegrationEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import DataUpdateCoordinator
    from .data import IntegrationConfigEntry

# Define the binary sensor entity configuration
# This creates a connectivity sensor that shows the integration's health status
ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key=DOMAIN,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform for the integration.

    This function is called by Home Assistant when the integration is loaded.
    It creates and registers binary sensor entities based on the entity
    descriptions defined above.

    Args:
        hass: The Home Assistant instance (unused but required by interface)
        entry: The config entry containing integration configuration and runtime data
        async_add_entities: Callback to register new entities with Home Assistant
    """
    # Create binary sensor entities from the coordinator
    # Each entity description results in one binary sensor entity
    async_add_entities(
        IntegrationBinarySensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IntegrationBinarySensor(IntegrationEntity, BinarySensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Binary sensor entity for Smart Cover Automation system health monitoring.

    This class creates a connectivity-style binary sensor that indicates whether
    the cover automation system is functioning properly. The sensor's state is
    automatically derived from the coordinator's operational status.

    The sensor provides:
    - Connectivity device class for appropriate UI representation
    - Automatic availability tracking based on coordinator health
    - Integration with Home Assistant's binary sensor platform

    State meanings:
    - 'on' (Connected): Automation system is working, coordinator is healthy
    - 'off' (Disconnected): Automation system has issues or coordinator failed
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides the health status for this sensor
            entity_description: Configuration describing the entity's properties
                               (name, device class, etc.)
        """
        # Initialize the base entity with coordinator integration
        super().__init__(coordinator)

        # Store the entity description that defines this sensor's characteristics
        self.entity_description = entity_description

    # Note: Multiple inheritance from IntegrationEntity (CoordinatorEntity) and
    # BinarySensorEntity causes a Pylance conflict on the 'available' property.
    # Both base classes define it differently, but they're compatible at runtime.
    # The CoordinatorEntity's implementation provides the correct coordinator-based
    # availability logic we want, so no override is needed.
