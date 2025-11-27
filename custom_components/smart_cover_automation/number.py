"""Number platform for smart_cover_automation.

This module provides number entities that allow users to configure various
numeric settings of the Smart Cover Automation integration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature

from .config import ConfKeys
from .const import DOMAIN, NUMBER_KEY_TEMP_THRESHOLD
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
    """Set up the number platform for the integration.

    This function is called by Home Assistant when the integration is loaded.
    It creates and registers all number entities for the integration.

    Args:
        hass: The Home Assistant instance (unused but required by interface)
        entry: The config entry containing integration configuration and runtime data
        async_add_entities: Callback to register new entities with Home Assistant
    """
    coordinator = entry.runtime_data.coordinator

    # Create all number entities
    entities = [
        TempThresholdNumber(coordinator),
    ]

    async_add_entities(entities)


#
# IntegrationNumber
#
class IntegrationNumber(IntegrationEntity, NumberEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Base number entity for Smart Cover Automation integration.

    This abstract base class provides common functionality for all number
    entities in the integration. It handles the basic entity setup and provides
    a foundation for specific number implementations.

    The class provides:
    - Integration with the coordinator for data updates
    - Automatic availability tracking based on coordinator status
    - Consistent entity naming and identification patterns
    - Integration with Home Assistant's number platform
    - Base methods for persisting number value changes in config options
    """

    #
    # __init__
    #
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: NumberEntityDescription,
        config_key: str,
    ) -> None:
        """Initialize the number entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this number entity
            entity_description: Configuration describing the entity's properties
                               (name, icon, min/max values, etc.)
            config_key: The configuration key this number entity controls
        """
        # Initialize the base entity with coordinator integration
        super().__init__(coordinator)

        # Store the entity description that defines this number's characteristics
        self.entity_description = entity_description

        # Store the config key this number entity controls
        self._config_key = config_key

        # Set unique ID to ensure proper device grouping and entity identification
        # This will result in entity_id: number.smart_cover_automation_{translation_key}
        self._attr_unique_id = f"{DOMAIN}_{entity_description.key}"

    # Note: We inherit the 'available' property from IntegrationEntity/CoordinatorEntity
    # which provides the correct coordinator-based availability logic.
    # No override is needed since the default behavior is exactly what we want.

    #
    # native_value
    #
    @property
    def native_value(self) -> float:  # pyright: ignore
        """Return the current value of the number entity.

        Reads from the resolved settings to get the current state.
        This reflects changes made through the integration's options flow.
        """
        resolved = self.coordinator._resolved_settings()
        return float(getattr(resolved, self._config_key.lower()))

    #
    # async_set_native_value
    #
    async def async_set_native_value(self, value: float) -> None:
        """Update the number entity value.

        Sets the config value and triggers a coordinator refresh
        to immediately apply the new setting.

        Args:
            value: The new value for the number entity
        """
        await self._async_persist_option(self._config_key, value)

    #
    # _async_persist_option
    #
    async def _async_persist_option(self, config_key: str, value: float) -> None:
        """Persist an option to the config entry.

        This method updates the integration's configuration options. The update
        will trigger the smart reload listener in __init__.py, which will
        intelligently decide whether to do a full reload or just refresh the
        coordinator based on which keys changed.

        Args:
            config_key: The configuration key to update.
            value: The new value for the key.
        """
        entry = self.coordinator.config_entry
        current_options = dict(entry.options or {})
        current_options[config_key] = value

        # This will trigger the update listener (async_reload_entry) in __init__.py
        # which will compare configs and decide on refresh vs. reload
        self.coordinator.hass.config_entries.async_update_entry(entry, options=current_options)


#
# TempThresholdNumber
#
class TempThresholdNumber(IntegrationNumber):
    """Number entity for controlling the temperature threshold for heat protection."""

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the temperature threshold number entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                        and provides state management for this number entity
        """
        entity_description = NumberEntityDescription(
            key=NUMBER_KEY_TEMP_THRESHOLD,
            translation_key=NUMBER_KEY_TEMP_THRESHOLD,
            entity_category=EntityCategory.CONFIG,
            device_class=NumberDeviceClass.TEMPERATURE,
            icon="mdi:thermometer-lines",
            native_min_value=10,
            native_max_value=40,
            native_step=0.5,
            mode=NumberMode.BOX,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        )
        super().__init__(coordinator, entity_description, ConfKeys.TEMP_THRESHOLD.value)
