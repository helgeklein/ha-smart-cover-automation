"""Binary sensor platform for smart_cover_automation.

This module provides binary sensors that monitor various aspects of the
Smart Cover Automation integration. The binary sensors provide real-time
status information about the automation system's operation.

The sensors that appear in Home Assistant are:
- Entity: binary_sensor.smart_cover_automation_status - System status monitoring
- Entity: binary_sensor.smart_cover_automation_simulation_mode - Simulation mode status
"""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .const import BINARY_SENSOR_KEY_STATUS, DOMAIN
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

    # Note: Multiple inheritance from IntegrationEntity (CoordinatorEntity) and
    # BinarySensorEntity causes a Pylance conflict on the 'available' property.
    # Both base classes define it differently, but they're compatible at runtime.
    # The CoordinatorEntity's implementation provides the correct coordinator-based
    # availability logic we want, so no override is needed.


class StatusBinarySensor(IntegrationBinarySensor):
    """Binary sensor for monitoring Smart Cover Automation system health.

    This sensor indicates whether the cover automation system has any issues.
    The sensor's state is automatically derived from the coordinator's operational status.

    The sensor provides:
    - Problem device class for appropriate UI representation
    - Automatic availability tracking based on coordinator health
    - Integration with Home Assistant's binary sensor platform

    State meanings:
    - 'on' (Problem): Automation system has issues or coordinator failed
    - 'off' (OK): Automation system is working, coordinator is healthy
    """

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the status binary sensor.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                         and provides the status for this sensor
        """
        entity_description = BinarySensorEntityDescription(
            key=BINARY_SENSOR_KEY_STATUS,
            device_class=BinarySensorDeviceClass.PROBLEM,
            # icon="mdi:check-circle-outline",
            translation_key=BINARY_SENSOR_KEY_STATUS,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        super().__init__(coordinator, entity_description)

    @cached_property
    def is_on(self) -> bool:
        """Return True if the integration has problems.

        The binary sensor state reflects the coordinator's operational health:
        - True (on/Problem): Coordinator has failed or encountered errors
        - False (off/OK): Coordinator is successfully fetching and processing data

        This allows users to monitor automation system status and create
        automations based on system status. Note: Problem sensors use inverted logic.
        """
        return not self.coordinator.last_update_success
