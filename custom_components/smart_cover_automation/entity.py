"""Base entity class for Smart Cover Automation integration.

This module provides the foundation entity class that all platform entities
(sensors, switches, binary sensors) inherit from. It ensures consistent
coordinator integration, device grouping, and unique identification.
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import const
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

    # Mandatory: enable entity naming based on device name
    # Docs: https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/has-entity-name/
    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the entity.

        Args:
            coordinator: The DataUpdateCoordinator instance that manages
                        data updates and automation logic for this integration.
        """
        # Initialize the parent CoordinatorEntity to establish the link
        # between this entity and the coordinator for automatic updates
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return device info to group all integration entities under a single device.

        This property creates the device info lazily (only when accessed), which helps
        prevent potential duplicate device registry updates during HA startup when
        multiple entities are being initialized simultaneously.

        This makes the UI cleaner by showing all sensors, switches, and other
        entities as parts of one logical device rather than separate devices.
        Docs: https://developers.home-assistant.io/docs/device_registry_index/
        """
        return DeviceInfo(
            # Unique identifier for the device - use the config entry ID (a UUID)
            identifiers={(const.DOMAIN, self.coordinator.config_entry.entry_id)},
            name=const.INTEGRATION_NAME,
            model=const.INTEGRATION_NAME,
            entry_type=DeviceEntryType.SERVICE,
        )
