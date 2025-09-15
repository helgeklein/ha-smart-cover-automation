"""Base entity class for Smart Cover Automation integration.

This module provides the foundation entity class that all platform entities
(sensors, switches, binary sensors) inherit from. It ensures consistent
coordinator integration, device grouping, and unique identification.
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import DataUpdateCoordinator


class IntegrationEntity(CoordinatorEntity[DataUpdateCoordinator]):
    """Base entity class for Smart Cover Automation integration.

    This class serves as the foundation for all entities created by this integration.
    It provides:
    - Integration with the DataUpdateCoordinator for centralized data management
    - Unique entity identification using the config entry ID
    - Device grouping so all entities appear under a single device in Home Assistant

    All platform-specific entities (sensors, switches, binary sensors) should
    inherit from this class to ensure consistent behavior and proper coordinator
    integration.
    """

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the base integration entity.

        Args:
            coordinator: The DataUpdateCoordinator instance that manages
                        data updates and automation logic for this integration.
        """
        # Initialize the parent CoordinatorEntity to establish the link
        # between this entity and the coordinator for automatic updates
        super().__init__(coordinator)

        # Set unique ID using the config entry ID to ensure global uniqueness
        # within Home Assistant. This prevents conflicts with other integrations
        # or multiple instances of this integration.
        self._attr_unique_id = coordinator.config_entry.entry_id

        # Create device info to group all integration entities under a single device.
        # This makes the UI cleaner by showing all sensors, switches, and other
        # entities as parts of one logical device rather than separate devices.
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    coordinator.config_entry.domain,  # Integration domain
                    coordinator.config_entry.entry_id,  # Unique entry identifier
                ),
            },
        )
