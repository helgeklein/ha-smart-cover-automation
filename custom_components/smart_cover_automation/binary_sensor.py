"""Binary sensor platform for smart_cover_automation.

This module provides a binary sensor that monitors the availability of the
Smart Cover Automation integration. The binary sensor
indicates whether the automation system is functioning properly by reflecting
the coordinator's last update status.

The sensor appears in Home Assistant as:
- Entity: binary_sensor.health_status
"""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .const import BINARY_SENSOR_KEY_HEALTH_STATUS, DOMAIN
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
    It creates and registers the health status binary sensor.

    Args:
        hass: The Home Assistant instance (unused but required by interface)
        entry: The config entry containing integration configuration and runtime data
        async_add_entities: Callback to register new entities with Home Assistant
    """
    # Create the health status binary sensor
    entity_description = BinarySensorEntityDescription(
        key=BINARY_SENSOR_KEY_HEALTH_STATUS,
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:check-circle-outline",
        translation_key=BINARY_SENSOR_KEY_HEALTH_STATUS,
    )

    async_add_entities(
        [
            IntegrationBinarySensor(
                coordinator=entry.runtime_data.coordinator,
                entity_description=entity_description,
            )
        ]
    )


class IntegrationBinarySensor(IntegrationEntity, BinarySensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Binary sensor entity for Smart Cover Automation system health monitoring.

    This class creates a problem-style binary sensor that indicates whether
    the cover automation system has any issues. The sensor's state is
    automatically derived from the coordinator's operational status.

    The sensor provides:
    - Problem device class for appropriate UI representation
    - Automatic availability tracking based on coordinator health
    - Integration with Home Assistant's binary sensor platform

    State meanings:
    - 'on' (Problem): Automation system has issues or coordinator failed
    - 'off' (OK): Automation system is working, coordinator is healthy
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

        # Override the unique ID or HA uses the device class ("problem") as instead of the key.
        # Expected resulting entity_id:
        # HA with English UI: binary_sensor.smart_cover_automation_health_status
        # HA with German UI: binary_sensor.smart_cover_automation_gesundheitsstatus
        self._attr_unique_id = f"{DOMAIN}_{entity_description.key}"

    @cached_property
    def is_on(self) -> bool:
        """Return True if the integration has problems.

        The binary sensor state reflects the coordinator's operational health:
        - True (on/Problem): Coordinator has failed or encountered errors
        - False (off/OK): Coordinator is successfully fetching and processing data

        This allows users to monitor automation system health and create
        automations based on system status. Note: Problem sensors use inverted logic.
        """
        return not self.coordinator.last_update_success

    # Note: Multiple inheritance from IntegrationEntity (CoordinatorEntity) and
    # BinarySensorEntity causes a Pylance conflict on the 'available' property.
    # Both base classes define it differently, but they're compatible at runtime.
    # The CoordinatorEntity's implementation provides the correct coordinator-based
    # availability logic we want, so no override is needed.
