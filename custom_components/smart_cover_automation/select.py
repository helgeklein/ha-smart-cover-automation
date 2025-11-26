"""Select platform for smart_cover_automation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory

from . import const
from .const import (
    DOMAIN,
    SELECT_KEY_LOCK_MODE,
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
    hass: HomeAssistant,
    entry: IntegrationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""

    coordinator = entry.runtime_data.coordinator

    entities = [
        LockModeSelect(coordinator),
    ]

    async_add_entities(entities)


#
# IntegrationSelect
#
class IntegrationSelect(IntegrationEntity, SelectEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Base select entity."""

    #
    # __init__
    #
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: SelectEntityDescription,
    ) -> None:
        """Initialize the sensor entity.

        Args:
            coordinator: The DataUpdateCoordinator that manages automation logic
                         and provides data for this select
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


#
# LockModeSelect
#
class LockModeSelect(IntegrationSelect):
    """Select entity for choosing lock mode."""

    #
    # __init__
    #
    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        super().__init__(
            coordinator,
            SelectEntityDescription(
                key=SELECT_KEY_LOCK_MODE,
                translation_key=SELECT_KEY_LOCK_MODE,
                icon="mdi:lock",
                entity_category=EntityCategory.CONFIG,
            ),
        )

        self._attr_options = [mode.value for mode in const.LockMode]

    #
    # current_option
    #
    @property
    def current_option(self) -> str | None:  # pyright: ignore
        """Return current lock mode."""

        return self.coordinator.lock_mode

    #
    # async_select_option
    #
    async def async_select_option(self, option: str) -> None:
        """Change the lock mode."""

        # Convert string to LockMode enum
        try:
            lock_mode = const.LockMode(option)
        except ValueError:
            const.LOGGER.error(f"Invalid lock mode value: {option}")
            return

        await self.coordinator.async_set_lock_mode(lock_mode)
