"""Select platform for smart_cover_automation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory

from .const import (
    DOMAIN,
    SELECT_KEY_LOCK_MODE,
    LockMode,
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


class IntegrationSelect(IntegrationEntity, SelectEntity):
    """Base select entity."""

    #
    # __init__
    #
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entity_description: SelectEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{DOMAIN}_{entity_description.key}"


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
                name="Lock Mode",
                icon="mdi:lock",
                entity_category=EntityCategory.CONFIG,
            ),
        )

        self._attr_options = [mode.value for mode in LockMode]

    #
    # current_option
    #
    @property
    def current_option(self) -> str:
        """Return current lock mode."""

        return self.coordinator.lock_mode

    #
    # async_select_option
    #
    async def async_select_option(self, option: str) -> None:
        """Change the lock mode."""

        await self.coordinator.async_set_lock_mode(option)
